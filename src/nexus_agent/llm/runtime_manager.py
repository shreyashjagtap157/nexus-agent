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
    },
    "cuda": {
        "name": "llama-cpp-python (CUDA)",
        "package": "llama-cpp-python",
        "extras": "cuda",
        "description": "NVIDIA GPU acceleration via CUDA",
        "cmake_args": "-DLLAMA_CUDA=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
    },
    "vulkan": {
        "name": "llama-cpp-python (Vulkan)",
        "package": "llama-cpp-python",
        "extras": "vulkan",
        "description": "Cross-platform GPU via Vulkan",
        "cmake_args": "-DLLAMA_VULKAN=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
    },
    "metal": {
        "name": "llama-cpp-python (Metal)",
        "package": "llama-cpp-python",
        "extras": "metal",
        "description": "Apple Silicon GPU via Metal",
        "cmake_args": "-DLLAMA_METAL=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
    },
    "rocm": {
        "name": "llama-cpp-python (ROCm)",
        "package": "llama-cpp-python",
        "extras": "rocm",
        "description": "AMD GPU via ROCm",
        "cmake_args": "-DLLAMA_HIPBLAS=ON;-DLLAMA_NATIVE=ON",
        "pip_install_args": "",
    },
    "onnx": {
        "name": "ONNX Runtime GenAI",
        "package": "onnxruntime-genai",
        "extras": "",
        "description": "ONNX model runtime with DirectML support",
        "cmake_args": "",
        "pip_install_args": "onnxruntime-genai onnxruntime-directml",
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

    def __post_init__(self) -> None:
        valid_runtimes = {"auto", "llama-cpp", "onnx"}
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

        self._active_engine: LLMProvider | None = None

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
    def get_installable_runtimes() -> dict[str, dict[str, Any]]:
        """Return dict of installable runtimes keyed by backend name."""
        return dict(INSTALLABLE_RUNTIMES)

    @staticmethod
    def is_runtime_installed(backend: str) -> bool:
        """Check if a given runtime backend is already installed."""
        if backend == "cpu":
            try:
                import llama_cpp  # noqa: F401
                return True
            except ImportError:
                return False
        elif backend == "cuda":
            try:
                import llama_cpp
                return hasattr(llama_cpp, "llama_supports_gpu_offload") and llama_cpp.llama_supports_gpu_offload()
            except ImportError:
                return False
        elif backend == "onnx":
            try:
                import onnxruntime  # noqa: F401
                return True
            except ImportError:
                return False
        elif backend == "vulkan":
            try:
                import llama_cpp
                return "vulkan" in str(getattr(llama_cpp, "__git_revision__", "")).lower()
            except ImportError:
                return False
        elif backend == "metal":
            try:
                import llama_cpp
                return "metal" in str(getattr(llama_cpp, "__git_revision__", "")).lower()
            except ImportError:
                return False
        elif backend == "rocm":
            try:
                import llama_cpp
                return "hip" in str(getattr(llama_cpp, "__git_revision__", "")).lower() or "rocm" in str(getattr(llama_cpp, "__git_revision__", "")).lower()
            except ImportError:
                return False
        return False

    @staticmethod
    def install_runtime(backend: str, force_reinstall: bool = False, progress_callback: Any = None) -> bool:
        """Install a runtime backend via pip.

        Args:
            backend: Runtime backend key (cpu, cuda, vulkan, metal, rocm, onnx).
            force_reinstall: Reinstall even if already installed.
            progress_callback: Optional callable(status, detail) for progress reporting.

        Returns:
            True if installation succeeded.
        """
        rt = INSTALLABLE_RUNTIMES.get(backend)
        if not rt:
            raise ValueError(f"Unknown runtime backend: {backend}. Choose from: {', '.join(INSTALLABLE_RUNTIMES.keys())}")

        if not force_reinstall and RuntimeManager.is_runtime_installed(backend):
            logger.info(f"Runtime {rt['name']} is already installed. Use force_reinstall=True to reinstall.")
            return True

        if progress_callback:
            progress_callback("installing", f"Installing {rt['name']}...")

        package_spec = rt["package"]
        if rt.get("extras"):
            package_spec = f"{rt['package']}[{rt['extras']}]"

        pip_args = [sys.executable, "-m", "pip", "install"]
        if force_reinstall:
            pip_args.append("--force-reinstall")

        if rt.get("cmake_args"):
            env = {"CMAKE_ARGS": rt["cmake_args"]}
        else:
            env = {}

        if rt.get("pip_install_args"):
            pip_args.extend(rt["pip_install_args"].split())
        else:
            pip_args.append(package_spec)

        try:
            result = subprocess.run(
                pip_args,
                env={**env} if env else None,
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
                progress_callback("verifying", f"Verifying {rt['name']}...")

            try:
                importlib.invalidate_caches()
                if not RuntimeManager.is_runtime_installed(backend):
                    checked = RuntimeManager._verify_runtime_import(backend)
                    if not checked:
                        logger.warning(f"Runtime {backend} installed but import verification inconclusive")
            except ImportError:
                logger.warning(f"Runtime {backend} installed but could not verify import")

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
    def _verify_runtime_import(backend: str) -> bool:
        """Try to import a runtime after installation."""
        try:
            if backend == "cpu":
                import llama_cpp  # noqa: F401
                return True
            elif backend == "cuda":
                import llama_cpp  # noqa: F401
                return hasattr(llama_cpp, "llama_supports_gpu_offload") and llama_cpp.llama_supports_gpu_offload()
            elif backend == "onnx":
                import onnxruntime  # noqa: F401
                return True
            elif backend in ("vulkan", "metal", "rocm"):
                import llama_cpp  # noqa: F401
                return True
            return False
        except ImportError:
            return False

    @staticmethod
    def uninstall_runtime(backend: str) -> bool:
        """Uninstall a runtime backend via pip."""
        rt = INSTALLABLE_RUNTIMES.get(backend)
        if not rt:
            raise ValueError(f"Unknown runtime backend: {backend}")

        pip_args = [sys.executable, "-m", "pip", "uninstall", "-y"]
        pip_args.append(rt["package"])

        try:
            result = subprocess.run(pip_args, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error(f"Failed to uninstall {rt['name']}: {result.stderr}")
                return False
            importlib.invalidate_caches()
            logger.info(f"Uninstalled {rt['name']}")
            return True
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as e:
            logger.error(f"Uninstall error for {rt['name']}: {e}")
            return False

    def switch_runtime(self, backend: str) -> bool:
        """Switch the active runtime backend.

        Unlike select_engine() which takes a model path, this changes the
        runtime type used for future engine selections.

        Args:
            backend: Runtime backend key (auto, llama-cpp, onnx).

        Returns:
            True if switch was successful.
        """
        valid = {"auto", "llama-cpp", "onnx"}
        if backend.lower() not in valid:
            logger.error(f"Invalid runtime: {backend}. Valid: {', '.join(valid)}")
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
