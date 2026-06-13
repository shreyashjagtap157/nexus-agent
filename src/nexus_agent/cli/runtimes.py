"""Runtime detection — scans for available LLM backends on the system."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RuntimeInfo:
    name: str
    provider: str
    available: bool
    path: str = ""
    version: str = ""
    description: str = ""
    priority: int = 0


_ALLOWED_RUNTIME_DIRS = [
    "/usr/bin", "/usr/local/bin", "/usr/local/cuda/bin",
    "/opt/cuda/bin", "/opt/rocm/bin",
    "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA",
    "C:\\Program Files\\NVIDIA Corporation",
    "C:\\Program Files\\VulkanSDK",
    "C:\\Windows\\System32",
]


def _validate_runtime_path(path: str) -> bool:
    """Validate that a resolved runtime path is a real executable file."""
    if not os.path.isfile(path) and not os.path.isdir(path):
        return False
    if not os.path.exists(path):
        return False
    return True


def _which(name: str) -> str | None:
    return shutil.which(name)


def _check_cuda() -> list[RuntimeInfo]:
    runtimes = []
    nvcc = _which("nvcc")
    if nvcc and _validate_runtime_path(nvcc):
        try:
            result = subprocess.run([nvcc, "--version"], capture_output=True, text=True, timeout=5)
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            runtimes.append(RuntimeInfo(
                name="CUDA (nvcc compiler)", provider="cuda",
                available=True, path=nvcc, version=version,
                description="NVIDIA CUDA compiler", priority=90,
            ))
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Check for llama.cpp CUDA build
    llama_cuda = _which("llama-cli") or _which("llama-server")
    if llama_cuda:
        runtimes.append(RuntimeInfo(
            name="llama.cpp (CUDA)", provider="cuda",
            available=True, path=llama_cuda,
            description="llama.cpp with CUDA support", priority=85,
        ))
    # Check CUDA toolkit path
    cuda_path = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
    if cuda_path:
        ver_path = os.path.join(cuda_path, "version.txt")
        version = ""
        if os.path.isfile(ver_path):
            try:
                with open(ver_path, encoding="utf-8") as f:
                    version = f.read().strip()
            except (OSError, UnicodeDecodeError):
                pass
        runtimes.append(RuntimeInfo(
            name="CUDA Toolkit", provider="cuda",
            available=True, path=cuda_path, version=version,
            description=f"CUDA SDK at {cuda_path}", priority=80,
        ))
    return runtimes


def _check_vulkan() -> list[RuntimeInfo]:
    runtimes = []
    # Check for Vulkan SDK / loader
    vulkan_info = _which("vulkaninfo")
    if vulkan_info and _validate_runtime_path(vulkan_info):
        try:
            subprocess.run([vulkan_info, "--summary"], capture_output=True, text=True, timeout=5)
            runtimes.append(RuntimeInfo(
                name="Vulkan", provider="vulkan",
                available=True, path=vulkan_info,
                description="Vulkan SDK detected", priority=70,
            ))
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Check for llama.cpp Vulkan build
    llama_vulkan = _which("llama-vulkan")
    if llama_vulkan:
        runtimes.append(RuntimeInfo(
            name="llama.cpp (Vulkan)", provider="vulkan",
            available=True, path=llama_vulkan,
            description="llama.cpp with Vulkan support", priority=75,
        ))
    # DirectML / NPU
    if os.name == "nt":
        directml = _which("onnxruntime")
        if not directml:
            try:
                import onnxruntime
                directml = onnxruntime.__file__
            except ImportError:
                directml = None
        if directml:
            runtimes.append(RuntimeInfo(
                name="DirectML (NPU/GPU)", provider="npu",
                available=True, path=directml,
                description="ONNX Runtime with DirectML", priority=60,
            ))
    return runtimes


def _check_cpu() -> list[RuntimeInfo]:
    runtimes = []
    # llama.cpp CPU build
    llama = _which("llama-cli") or _which("llama-server") or _which("llama.cpp")
    if llama:
        runtimes.append(RuntimeInfo(
            name="llama.cpp (CPU)", provider="local",
            available=True, path=llama,
            description="llama.cpp CPU backend", priority=50,
        ))
    # llama-cpp-python Python package
    try:
        import llama_cpp
        runtimes.append(RuntimeInfo(
            name="llama-cpp-python", provider="local",
            available=True, path=llama_cpp.__file__,
            description="Python bindings for llama.cpp", priority=55,
        ))
    except ImportError:
        pass
    # Transformers / Optimum
    try:
        import transformers
        runtimes.append(RuntimeInfo(
            name="HuggingFace Transformers", provider="local",
            available=True, path=transformers.__file__,
            description="HF Transformers (CPU/GPU)", priority=40,
        ))
    except ImportError:
        pass
    runtimes.append(RuntimeInfo(
        name="CPU (default)", provider="local",
        available=True, path="builtin",
        description="Default CPU provider (always available)", priority=10,
    ))
    return runtimes


def _check_rocm() -> list[RuntimeInfo]:
    runtimes = []
    rocm_path = os.environ.get("ROCM_PATH") or os.environ.get("ROCM_HOME")
    if rocm_path and os.path.isdir(rocm_path):
        runtimes.append(RuntimeInfo(
            name="ROCm", provider="rocm",
            available=True, path=rocm_path,
            description="AMD ROCm SDK", priority=65,
        ))
    return runtimes


def _check_openvino() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import openvino
        runtimes.append(RuntimeInfo(
            name="OpenVINO", provider="openvino",
            available=True, path=openvino.__file__,
            description="Intel OpenVINO toolkit", priority=45,
        ))
    except ImportError:
        pass
    return runtimes


def _check_tpu() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import jax
        runtimes.append(RuntimeInfo(
            name="JAX (TPU/GPU)", provider="tpu",
            available=True, path=jax.__file__,
            description="Google JAX runtime", priority=35,
        ))
    except ImportError:
        pass
    return runtimes


def _check_vllm() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import vllm
        runtimes.append(RuntimeInfo(
            name="vLLM", provider="vllm",
            available=True, path=vllm.__file__,
            description="High-throughput LLM serving with PagedAttention", priority=85,
        ))
    except ImportError:
        pass
    # Check if vLLM server is running
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8000/v1/models", method="GET")
        urllib.request.urlopen(req, timeout=1)
        runtimes.append(RuntimeInfo(
            name="vLLM (running)", provider="vllm",
            available=True, path="http://localhost:8000",
            description="vLLM server is active", priority=90,
        ))
    except Exception:
        pass
    return runtimes


def _check_sglang() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import sglang
        runtimes.append(RuntimeInfo(
            name="SGLang", provider="sglang",
            available=True, path=sglang.__file__,
            description="Structured generation language for LLMs", priority=80,
        ))
    except ImportError:
        pass
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:30000/v1/models", method="GET")
        urllib.request.urlopen(req, timeout=1)
        runtimes.append(RuntimeInfo(
            name="SGLang (running)", provider="sglang",
            available=True, path="http://localhost:30000",
            description="SGLang server is active", priority=85,
        ))
    except Exception:
        pass
    return runtimes


def _check_mlx() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import mlx
        runtimes.append(RuntimeInfo(
            name="MLX (Apple Silicon)", provider="mlx",
            available=True, path=mlx.__file__,
            description="Apple ML framework by Apple ML Research", priority=75,
        ))
    except ImportError:
        pass
    try:
        import mlx_lm
        runtimes.append(RuntimeInfo(
            name="MLX LM", provider="mlx",
            available=True, path=mlx_lm.__file__,
            description="MLX language model inference", priority=80,
        ))
    except ImportError:
        pass
    return runtimes


def _check_external_servers() -> list[RuntimeInfo]:
    """Check for running external LLM servers (Ollama, LM Studio, KoboldCpp)."""
    import urllib.request
    runtimes = []
    probes = [
        ("Ollama", "ollama", "http://localhost:11434/api/tags", "Local LLM server"),
        ("LM Studio", "lm_studio", "http://localhost:1234/v1/models", "Desktop LLM app with API"),
        ("KoboldCpp", "koboldcpp", "http://localhost:5001/v1/models", "GGUF inference server"),
        ("TabbyAPI (ExLlamaV2)", "exllamav2", "http://localhost:5000/v1/models", "ExLlamaV2 inference API"),
    ]
    for name, provider, url, desc in probes:
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=1)
            runtimes.append(RuntimeInfo(
                name=f"{name} (running)", provider=provider,
                available=True, path=url,
                description=desc, priority=75,
            ))
        except Exception:
            pass
    # Check if Ollama CLI is installed
    import shutil
    if shutil.which("ollama"):
        runtimes.append(RuntimeInfo(
            name="Ollama CLI", provider="ollama",
            available=True, path=shutil.which("ollama") or "",
            description="Ollama command-line tool", priority=70,
        ))
    return runtimes


def _check_tensorrt() -> list[RuntimeInfo]:
    runtimes = []
    try:
        import tensorrt_llm
        runtimes.append(RuntimeInfo(
            name="TensorRT-LLM", provider="tensorrt_llm",
            available=True, path=tensorrt_llm.__file__,
            description="NVIDIA TensorRT for LLM (Docker recommended)", priority=60,
        ))
    except ImportError:
        pass
    # Check for Docker image
    import shutil
    if shutil.which("docker"):
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "tensorrt_llm"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                runtimes.append(RuntimeInfo(
                    name="TensorRT-LLM (Docker)", provider="tensorrt_llm",
                    available=True, path="docker:tensorrt_llm",
                    description="TensorRT-LLM Docker image detected", priority=65,
                ))
        except Exception:
            pass
    return runtimes


def scan_runtimes() -> list[RuntimeInfo]:
    """Scan all available runtimes on the system."""
    all_runtimes = []
    all_runtimes.extend(_check_cpu())
    all_runtimes.extend(_check_cuda())
    all_runtimes.extend(_check_vulkan())
    all_runtimes.extend(_check_rocm())
    all_runtimes.extend(_check_openvino())
    all_runtimes.extend(_check_tpu())
    all_runtimes.extend(_check_vllm())
    all_runtimes.extend(_check_sglang())
    all_runtimes.extend(_check_mlx())
    all_runtimes.extend(_check_external_servers())
    all_runtimes.extend(_check_tensorrt())
    return sorted(all_runtimes, key=lambda r: (-r.priority, r.name))


def format_runtime_list(runtimes: list[RuntimeInfo]) -> str:
    """Format runtimes for display."""
    lines = []
    for rt in runtimes:
        status = "✓" if rt.available else "✗"
        ver = f" [{rt.version}]" if rt.version else ""
        lines.append(f"  {status} [bold]{rt.name}[/bold]{ver}")
        lines.append(f"    [dim]{rt.description}[/dim]")
        if rt.path and rt.path != "builtin":
            lines.append(f"    [dim]Path: {rt.path}[/dim]")
    return "\n".join(lines) if lines else "  [dim]No runtimes detected[/dim]"
