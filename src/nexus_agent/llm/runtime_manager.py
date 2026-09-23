"""
Runtime Manager — Selects and instantiates the correct local LLM runtime.

Switches dynamically between llama.cpp (GGUF), ONNX Runtime GenAI (ONNX/NPU),
and Ollama depending on configuration and model format.

Includes the SmartRouter for cost/latency-aware provider selection and automatic fallback chains.
"""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from nexus_agent.llm.base import LLMProvider
from nexus_agent.llm.local_engine import LocalEngine
from nexus_agent.llm.onnx_engine import ONNX_AVAILABLE, OnnxEngine

logger = logging.getLogger(__name__)

INSTALLABLE_RUNTIMES: dict[str, dict[str, Any]] = {
    "cpu": {
        "name": "llama-cpp-python (CPU)",
        "package": "llama-cpp-python",
        "extras": "",
        "description": "Standard CPU-only build — works on all systems",
        "cmake_args": "-DLLAMA_NATIVE=ON;-DLLAMA_AVX512=OFF",
        "pip_install_args": "",
        "runtime_type": "llama_cpp",
    },
    "cuda": {
        "name": "llama-cpp-python (CUDA)",
        "package": "llama-cpp-python",
        "extras": "cuda",
        "description": "NVIDIA GPU acceleration via CUDA",
        "cmake_args": "-DLLAMA_CUDA=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
        "runtime_type": "llama_cpp",
    },
    "vulkan": {
        "name": "llama-cpp-python (Vulkan)",
        "package": "llama-cpp-python",
        "extras": "vulkan",
        "description": "Cross-platform GPU via Vulkan",
        "cmake_args": "-DLLAMA_VULKAN=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
        "runtime_type": "llama_cpp",
    },
    "metal": {
        "name": "llama-cpp-python (Metal)",
        "package": "llama-cpp-python",
        "extras": "metal",
        "description": "Apple Silicon GPU via Metal",
        "cmake_args": "-DLLAMA_METAL=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
        "runtime_type": "llama_cpp",
    },
    "rocm": {
        "name": "llama-cpp-python (ROCm)",
        "package": "llama-cpp-python",
        "extras": "rocm",
        "description": "AMD GPU via ROCm",
        "cmake_args": "-DLLAMA_HIPBLAS=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
        "runtime_type": "llama_cpp",
    },
    "onnx": {
        "name": "ONNX Runtime GenAI",
        "package": "onnxruntime-genai",
        "extras": "",
        "description": "ONNX model runtime with DirectML support",
        "cmake_args": "",
        "pip_install_args": "onnxruntime-genai onnxruntime-directml",
        "runtime_type": "onnx",
    },
    # ── Phase 3: New Runtimes ──────────────────────────────────────
    "ollama": {
        "name": "Ollama",
        "package": "",
        "extras": "",
        "description": "Local LLM server with built-in model management (ollama.com)",
        "cmake_args": "",
        "pip_install_args": "",
        "runtime_type": "external_server",
        "probe_url": "http://localhost:11434/api/tags",
    },
    "vllm": {
        "name": "vLLM",
        "package": "vllm",
        "extras": "",
        "description": "High-throughput LLM serving with PagedAttention",
        "cmake_args": "",
        "pip_install_args": "vllm",
        "runtime_type": "python_package",
        "probe_url": "http://localhost:8000/v1/models",
    },
    "sglang": {
        "name": "SGLang",
        "package": "sglang",
        "extras": "",
        "description": "Structured generation language for LLMs",
        "cmake_args": "",
        "pip_install_args": "sglang[all]",
        "runtime_type": "python_package",
        "probe_url": "http://localhost:30000/v1/models",
    },
    "mlx": {
        "name": "MLX (Apple Silicon)",
        "package": "mlx-lm",
        "extras": "",
        "description": "Apple Silicon ML framework by Apple ML Research",
        "cmake_args": "",
        "pip_install_args": "mlx-lm",
        "runtime_type": "python_package",
    },
    "lm_studio": {
        "name": "LM Studio",
        "package": "",
        "extras": "",
        "description": "Local LLM desktop app with OpenAI-compatible API (lmstudio.ai)",
        "cmake_args": "",
        "pip_install_args": "",
        "runtime_type": "external_server",
        "probe_url": "http://localhost:1234/v1/models",
    },
    "exllamav2": {
        "name": "ExLlamaV2 (TabbyAPI)",
        "package": "exllamav2",
        "extras": "",
        "description": "Fast inference for quantized Llama models via TabbyAPI",
        "cmake_args": "",
        "pip_install_args": "exllamav2",
        "runtime_type": "python_package",
        "probe_url": "http://localhost:5000/v1/models",
    },
    "koboldcpp": {
        "name": "KoboldCpp",
        "package": "",
        "extras": "",
        "description": "GGUF inference server with OpenAI-compatible API",
        "cmake_args": "",
        "pip_install_args": "",
        "runtime_type": "external_server",
        "probe_url": "http://localhost:5001/v1/models",
    },
    "tensorrt_llm": {
        "name": "TensorRT-LLM (NVIDIA)",
        "package": "tensorrt_llm",
        "extras": "",
        "description": "NVIDIA TensorRT for LLM inference (Docker recommended)",
        "cmake_args": "",
        "pip_install_args": "tensorrt_llm",
        "runtime_type": "python_package",
    },
}


@dataclass
class LocalModelConfig:
    """Validated configuration for local model runtime settings."""
    runtime: str = "auto"
    gpu_backend: str = "auto"
    gpu_layers: int = -1
    context_size: int = 4096
    threads: int = 0
    chat_format: str = "auto"
    batch_size: int = 512
    use_mmap: bool = True
    use_mlock: bool = False
    default_model: str = ""
    seed: int = -1
    flash_attention: bool = True
    unified_kv_cache: bool = True
    rope_freq_base: float = 0.0
    rope_freq_scale: float = 0.0
    kv_quant_type: str = "f16"
    keep_in_memory: bool = True
    use_agent_protocol: bool = False
    reasoning_depth: int = 8

    def __post_init__(self) -> None:
        valid_runtimes = {
            "auto", "llama-cpp", "onnx",
            "ollama", "vllm", "sglang", "mlx",
            "lm_studio", "exllamav2", "koboldcpp", "tensorrt_llm",
        }
        runtime_lower = self.runtime.lower()
        if runtime_lower not in valid_runtimes:
            raise ValueError(f"Invalid runtime '{self.runtime}'. Must be one of {valid_runtimes}")
        valid_chat_formats = {
            "auto", "chatml", "chatml-function-calling",
            "functionary-v1", "functionary-v2",
            "llama-3-tool", "mistral-instruct", "command-r",
        }
        if self.chat_format not in valid_chat_formats:
            raise ValueError(f"Invalid chat_format '{self.chat_format}'. Must be one of {valid_chat_formats}")
        if self.context_size < 128:
            raise ValueError(f"context_size must be >= 128, got {self.context_size}")
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")


class RuntimeManager:
    """Orchestrates local runtime backends (llama.cpp, ONNX Runtime, Ollama)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the runtime manager with configuration.

        Args:
            config: Full application configuration dictionary.
        """
        self._config = config
        self._local_config = config.get("local_model", {})
        # Validate config via dataclass (extract only known keys)
        known_keys = {f.name for f in fields(LocalModelConfig)}
        filtered = {k: v for k, v in self._local_config.items() if k in known_keys}
        try:
            self._validated_config = LocalModelConfig(**filtered)
        except (TypeError, ValueError) as e:
            logger.warning(f"Local model config validation failed: {e}")
            self._validated_config = LocalModelConfig(**{k: v for k, v in filtered.items() if k in known_keys})
        self._runtime_override = self._validated_config.runtime
        self._gpu_backend = self._validated_config.gpu_backend
        self._gpu_layers = self._validated_config.gpu_layers
        self._context_size = self._validated_config.context_size
        self._threads = self._validated_config.threads
        self._chat_format = self._validated_config.chat_format
        self._batch_size = self._validated_config.batch_size
        self._use_mmap = self._validated_config.use_mmap
        self._use_mlock = self._validated_config.use_mlock
        self._seed = self._validated_config.seed
        self._flash_attention = self._validated_config.flash_attention
        self._unified_kv_cache = self._validated_config.unified_kv_cache
        self._rope_freq_base = self._validated_config.rope_freq_base
        self._rope_freq_scale = self._validated_config.rope_freq_scale
        self._kv_quant_type = self._validated_config.kv_quant_type
        self._keep_in_memory = self._validated_config.keep_in_memory
        self._use_agent_protocol = self._validated_config.use_agent_protocol
        self._reasoning_depth = self._validated_config.reasoning_depth

        self._active_engine: LLMProvider | None = None

        # Activate configured runtime backend if active is set
        active_backend = self._config.get("runtime", {}).get("active")
        if active_backend:
            RuntimeManager.activate_runtime(active_backend)

    @property
    def active_engine(self) -> LLMProvider | None:
        """Get the currently active engine."""
        return self._active_engine

    def select_engine(self, model_path: str | None = None) -> LLMProvider:
        """Select and initialize the appropriate runtime engine.

        Args:
            model_path: Path to the GGUF model file or ONNX model folder.
                        Defaults to configured default model.

        Returns:
            An LLMProvider instance (LocalEngine or OnnxEngine).
        """
        old_engine = self._active_engine

        target_path = model_path or self._local_config.get("default_model", "")
        if not target_path:
            raise ValueError("No model path specified. Set default_model in config or provide model_path.")
        resolved_path = Path(target_path).expanduser().resolve()

        runtime = self._runtime_override

        # Auto-detect runtime if set to auto
        if runtime == "auto":
            if resolved_path and resolved_path.is_dir() and (resolved_path / "genai_config.json").exists():
                runtime = "onnx"
            else:
                runtime = "llama-cpp"

        logger.info(f"Selecting local LLM runtime: {runtime}")

        # Activate the runtime backend in sys.path
        active_backend = self._config.get("runtime", {}).get("active")
        if not active_backend:
            if runtime == "onnx":
                active_backend = "onnx"
            else:
                for b in ["cuda", "vulkan", "cpu"]:
                    if RuntimeManager.is_runtime_installed(b):
                        active_backend = b
                        break
        if active_backend:
            RuntimeManager.activate_runtime(active_backend)

        try:
            if runtime == "onnx":
                if not ONNX_AVAILABLE:
                    logger.warning("ONNX Runtime is requested but not available. Falling back to llama.cpp.")
                    runtime = "llama-cpp"
                else:
                    new_engine = OnnxEngine(
                        model_path=str(resolved_path) if resolved_path else None,
                        context_size=self._context_size,
                        gpu_backend=self._gpu_backend,
                    )
                    # Successful instantiation! Close old engine and switch
                    if old_engine:
                        try:
                            old_engine.close()
                        except (OSError, RuntimeError) as e:
                            logger.warning(f"Error closing old LLM engine during switch: {e}")
                    self._active_engine = new_engine
                    return self._active_engine

            # Default/Fallback to llama-cpp (GGUF) engine
            new_engine = LocalEngine(
                model_path=str(resolved_path) if resolved_path else None,
                gpu_layers=self._gpu_layers,
                context_size=self._context_size,
                threads=self._threads,
                chat_format=self._chat_format,
                batch_size=self._batch_size,
                use_mmap=self._use_mmap,
                use_mlock=self._use_mlock,
                seed=self._seed,
                flash_attention=self._flash_attention,
                unified_kv_cache=self._unified_kv_cache,
                rope_freq_base=self._rope_freq_base,
                rope_freq_scale=self._rope_freq_scale,
                kv_quant_type=self._kv_quant_type,
                keep_in_memory=self._keep_in_memory,
                use_agent_protocol=self._use_agent_protocol,
                reasoning_depth=self._reasoning_depth,
                gpu_backend=self._gpu_backend,
            )
            # Successful instantiation! Close old engine and switch
            if old_engine:
                try:
                    old_engine.close()
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Error closing old LLM engine during switch: {e}")
            self._active_engine = new_engine
            return self._active_engine

        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to load new local engine runtime: {e}. Rolling back to old engine.")
            self._active_engine = old_engine
            raise RuntimeError(f"Failed to switch local engine: {e}") from e

    @staticmethod
    def activate_runtime(backend: str) -> None:
        """Prepend the isolated runtime directory to sys.path and invalidate caches."""
        import importlib
        import os
        if not backend or backend == "auto":
            return
        data_dir_path = os.path.expanduser("~/.nexus-agent")
        target_dir = os.path.join(data_dir_path, "runtimes", backend)
        if os.path.exists(target_dir):
            target_dir_abs = os.path.abspath(target_dir)
            if target_dir_abs not in sys.path:
                sys.path.insert(0, target_dir_abs)
                importlib.invalidate_caches()
                logger.info(f"Activated isolated runtime backend '{backend}' by prepending to sys.path: {target_dir_abs}")

    @staticmethod
    def get_recommended_runtimes() -> list[str]:
        """Detect and return a list of recommended runtimes for this machine."""
        recs = ["cpu"]
        import os
        import platform
        import shutil

        # Apple Silicon
        if sys.platform == "darwin":
            proc = platform.processor().lower()
            if any(x in proc for x in ("arm", "m1", "m2", "m3", "m4")):
                recs.append("metal")
                recs.append("mlx")

        # NVIDIA GPU
        has_nvidia = bool(
            shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
            or os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
        )
        if has_nvidia:
            recs.append("cuda")
            recs.append("onnx")
            recs.append("vllm")
            recs.append("tensorrt_llm")

        # Vulkan
        if shutil.which("vulkaninfo") or shutil.which("vulkaninfo.exe"):
            recs.append("vulkan")

        # Windows
        if sys.platform == "win32":
            recs.append("onnx")

        # Check for common external server runtimes
        for server, probe_key in [("ollama", "ollama"), ("lm_studio", "lm_studio"), ("koboldcpp", "koboldcpp")]:
            try:
                import urllib.request
                info = INSTALLABLE_RUNTIMES.get(server, {})
                probe = info.get("probe_url", "")
                if probe:
                    req = urllib.request.Request(probe, method="GET")
                    urllib.request.urlopen(req, timeout=1)
                    recs.append(probe_key)
            except Exception:
                pass

        return list(set(recs))

    @staticmethod
    def get_installable_runtimes() -> dict[str, dict[str, Any]]:
        """Return dict of installable runtimes keyed by backend name, with recommendations."""
        rts = dict(INSTALLABLE_RUNTIMES)
        recs = RuntimeManager.get_recommended_runtimes()
        for key in rts:
            rts[key]["recommended"] = (key in recs)
        return rts

    @staticmethod
    def is_runtime_installed(backend: str) -> bool:
        """Check if a given runtime backend is available.

        For isolated pip installs, checks the target directory.
        For external servers, probes the localhost endpoint.
        For system packages, checks import availability.
        """
        import os
        import shutil
        from pathlib import Path
        data_dir_path = os.path.expanduser("~/.nexus-agent")
        target_dir = Path(data_dir_path) / "runtimes" / backend

        # External servers — probe API endpoint
        if backend in ("ollama", "lm_studio", "koboldcpp"):
            info = INSTALLABLE_RUNTIMES.get(backend, {})
            probe_url = info.get("probe_url", "")
            if probe_url:
                try:
                    import urllib.request
                    req = urllib.request.Request(probe_url, method="GET")
                    urllib.request.urlopen(req, timeout=2)
                    return True
                except Exception:
                    pass
            # Fall back to checking if the binary/package exists
            if backend == "ollama" and shutil.which("ollama"):
                return True
            return False

        # Isolated pip installs
        if backend in ("cpu", "cuda", "vulkan", "metal", "rocm"):
            if not target_dir.exists():
                return False
            return (target_dir / "llama_cpp").exists() or list(target_dir.glob("llama_cpp*")) != []
        if backend == "onnx":
            if not target_dir.exists():
                return False
            return (target_dir / "onnxruntime_genai").exists() or list(target_dir.glob("onnxruntime_genai*")) != []

        # Python package runtimes (vLLM, SGLang, MLX, ExLlamaV2, TensorRT-LLM)
        pkg_map = {"vllm": "vllm", "sglang": "sglang", "mlx": "mlx", "exllamav2": "exllamav2", "tensorrt_llm": "tensorrt_llm"}
        pkg = pkg_map.get(backend)
        if pkg:
            try:
                importlib.import_module(pkg)
                return True
            except ImportError:
                pass
            if target_dir.exists() and list(target_dir.glob(f"{pkg}*")):
                return True

        return False

    @staticmethod
    def install_runtime(backend: str, force_reinstall: bool = False, progress_callback: Any = None) -> bool:
        """Install a runtime backend.

        For pip-installable runtimes: installs to isolated target directory.
        For external servers: prints instructions (Ollama, LM Studio, KoboldCpp).
        """
        import os
        import shutil
        from pathlib import Path
        rt = INSTALLABLE_RUNTIMES.get(backend)
        if not rt:
            raise ValueError(f"Unknown runtime backend: {backend}. Choose from: {', '.join(INSTALLABLE_RUNTIMES.keys())}")

        runtime_type = rt.get("runtime_type", "")

        # External servers — just print install instructions
        if runtime_type == "external_server":
            install_guides = {
                "ollama": "Visit https://ollama.com to download and install, then run: ollama pull <model>",
                "lm_studio": "Download from https://lmstudio.ai and enable the local API server in Settings.",
                "koboldcpp": "Download from https://github.com/LostRuins/koboldcpp/releases and run with --openai-compat.",
            }
            guide = install_guides.get(backend, f"Download and install {rt['name']} manually.")
            if progress_callback:
                progress_callback("info", guide)
            logger.info("External server runtime '%s': %s", backend, guide)
            return True

        # External binary — check if available on PATH
        if backend == "ollama" and shutil.which("ollama"):
            if progress_callback:
                progress_callback("complete", f"{rt['name']} is already installed (found on PATH)")
            return True

        data_dir_path = os.path.expanduser("~/.nexus-agent")
        target_dir = Path(data_dir_path) / "runtimes" / backend

        if not force_reinstall and RuntimeManager.is_runtime_installed(backend):
            logger.info(f"Runtime {rt['name']} is already installed. Use force_reinstall=True to reinstall.")
            if progress_callback:
                progress_callback("complete", f"{rt['name']} is already installed")
            return True

        if progress_callback:
            progress_callback("installing", f"Installing {rt['name']} in isolated path...")

        target_dir.mkdir(parents=True, exist_ok=True)
        package_spec = rt["package"]
        if rt.get("extras"):
            package_spec = f"{rt['package']}[{rt['extras']}]"

        pip_args = [sys.executable, "-m", "pip", "install", "--target", str(target_dir)]
        if force_reinstall:
            pip_args.append("--upgrade")

        if rt.get("cmake_args"):
            env = {"CMAKE_ARGS": rt["cmake_args"]}
        else:
            env = {}

        if rt.get("pip_install_args"):
            pkgs = rt["pip_install_args"].split()
            pip_args.extend(pkgs)
        else:
            pip_args.append(package_spec)

        try:
            current_env = dict(os.environ)
            if env:
                current_env.update(env)

            result = subprocess.run(
                pip_args,
                env=current_env,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error(f"Failed to install {rt['name']}: {result.stderr}")
                if progress_callback:
                    progress_callback("error", f"Installation failed: {result.stderr[-200:]}")
                return False

            if progress_callback:
                progress_callback("complete", f"{rt['name']} installed successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Installation of {rt['name']} timed out (10 minutes)")
            if progress_callback:
                progress_callback("error", "Installation timed out")
            return False
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Installation error for {rt['name']}: {e}")
            if progress_callback:
                progress_callback("error", str(e))
            return False

    @staticmethod
    def uninstall_runtime(backend: str) -> bool:
        """Uninstall a runtime backend by removing its isolated directory."""
        import os
        import shutil
        from pathlib import Path
        data_dir_path = os.path.expanduser("~/.nexus-agent")
        target_dir = Path(data_dir_path) / "runtimes" / backend
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir)
                logger.info(f"Uninstalled runtime {backend} from {target_dir}")
                return True
            except OSError as e:
                logger.error(f"Failed to delete directory {target_dir}: {e}")
                return False
        return True

    def switch_runtime(self, backend: str) -> bool:
        """Switch the active runtime backend.

        Args:
            backend: Runtime backend key.

        Returns:
            True if switch was successful.
        """
        valid = {"auto", "llama-cpp", "onnx", "ollama", "vllm", "sglang",
                 "mlx", "lm_studio", "exllamav2", "koboldcpp", "tensorrt_llm"}
        if backend.lower() not in valid:
            logger.error(f"Invalid runtime: {backend}. Valid: {', '.join(sorted(valid))}")
            return False

        self._runtime_override = backend.lower()
        self._config.setdefault("local_model", {})["runtime"] = backend.lower()
        logger.info(f"Runtime switched to: {backend}")
        return True

    def close(self) -> None:
        """Clean up active runtime engine."""
        if self._active_engine:
            try:
                self._active_engine.close()
            except (OSError, RuntimeError) as e:
                logger.warning(f"Error closing LLM engine: {e}")
            finally:
                self._active_engine = None

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, RuntimeError):
            pass


class SmartRouter:
    """Intelligent cost-aware and latency-aware dynamic routing selector for multiple providers.

    Routes simple tasks to local or fast cloud APIs, complex tasks to rich intelligence engines,
    and runs fallbacks sequentially in the event of failures.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        # Track response duration averages: default initial values in seconds
        self._response_times: dict[str, float] = {
            "local": 0.5,
            "ollama": 0.3,
            "groq": 0.2,
            "openai": 1.2,
            "anthropic": 1.5,
            "google": 0.8
        }
        # Fallback order of providers
        self.fallback_chain = ["local", "ollama", "groq", "google", "openai", "anthropic"]

    def update_latency(self, provider: str, duration: float) -> None:
        """Dynamically update recorded average latency / response time for a provider."""
        p_key = provider.lower()
        if p_key in self._response_times:
            # Exponential moving average (alpha = 0.3)
            self._response_times[p_key] = (0.7 * self._response_times[p_key]) + (0.3 * duration)
        else:
            self._response_times[p_key] = duration

    def select_provider(self, task_complexity: str = "medium") -> str:
        """Route task to correct provider based on complexity, cost/latency profile.

        Complexity tiers:
        - 'low': Fast status, simple file read, code formatting -> local/groq/ollama
        - 'medium': Edits, bug fixes, refactoring -> google/openai/local
        - 'high': Large architectural planning, debate review -> anthropic/openai
        """
        c_tier = task_complexity.lower()

        if c_tier == "low":
            # Pick fastest of local/ollama/groq
            candidates = ["groq", "ollama", "local"]
            return self._get_fastest_candidate(candidates)
        elif c_tier == "medium":
            # Balance capability with cost
            candidates = ["google", "openai", "local"]
            return self._get_fastest_candidate(candidates)
        else:
            # High complexity requires best intelligence
            candidates = ["anthropic", "openai"]
            return self._get_fastest_candidate(candidates)

    def _get_fastest_candidate(self, candidates: list[str]) -> str:
        """Find the provider with the lowest tracked latency among active options."""
        best_provider = "local"
        best_time = 9999.0

        for cand in candidates:
            if cand in self._response_times:
                t = self._response_times[cand]
                if t < best_time:
                    best_time = t
                    best_provider = cand

        return best_provider

    def get_fallback_chain(self, failing_provider: str) -> list[str]:
        """Produce the fallback providers sequence list excluding the failing one."""
        p = failing_provider.lower()
        return [f for f in self.fallback_chain if f != p]
