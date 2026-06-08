"""Hardware and model capability detection for NexusAgent.

Probes the system for GPU presence, VRAM, CPU features, RAM,
and uses that data to determine which runtimes and models are viable.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HardwareCapabilities:
    """Detected hardware capabilities of the current system."""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_features: list[str] = field(default_factory=list)
    ram_gb: float = 0.0
    has_cuda: bool = False
    cuda_version: str = ""
    vram_gb: float = 0.0
    gpu_count: int = 0
    gpu_names: list[str] = field(default_factory=list)
    has_rocm: bool = False
    has_metal: bool = False
    has_vulkan: bool = False
    has_openvino: bool = False
    is_apple_silicon: bool = False
    is_windows: bool = False
    is_linux: bool = False
    is_macos: bool = False


@dataclass
class ModelCapabilityProfile:
    """Profile of what a model/provider can do, based on hardware + model type."""
    supports_tool_calling: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_system_message: bool = True
    supports_parallel_tool_calls: bool = False
    supports_structured_output: bool = False
    supports_function_calling: bool = False
    max_context_length: int = 4096
    max_output_tokens: int = 4096
    recommended_batch_size: int = 512
    recommended_gpu_layers: int = -1
    tokenizer_type: str = ""
    runtime_type: str = "llama_cpp"
    model_format: str = "gguf"

    # Hardware-driven recommendations
    estimated_tokens_per_sec: float = 0.0
    max_model_size_gb: float = 0.0
    memory_available_gb: float = 0.0


def detect_hardware() -> HardwareCapabilities:
    """Probe the current system for hardware capabilities.

    Returns:
        HardwareCapabilities dataclass with detected values.
    """
    caps = HardwareCapabilities()

    # OS detection
    sys_platform = platform.system().lower()
    caps.is_windows = sys_platform == "windows"
    caps.is_linux = sys_platform == "linux"
    caps.is_macos = sys_platform == "darwin"

    # CPU
    caps.cpu_cores = os.cpu_count() or 0
    try:
        if caps.is_linux:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("flags"):
                        caps.cpu_features = line.split(":")[1].strip().split()
                        break
        elif caps.is_macos:
            result = subprocess.run(["sysctl", "-n", "machdep.cpu.features"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                caps.cpu_features = result.stdout.strip().split()
        caps.cpu_threads = caps.cpu_cores * 2 if any(f in caps.cpu_features for f in ("ht", "HTT")) else caps.cpu_cores
    except Exception:
        caps.cpu_threads = caps.cpu_cores

    # RAM
    try:
        if caps.is_linux:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        caps.ram_gb = kb / (1024 * 1024)
                        break
        elif caps.is_macos:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                caps.ram_gb = int(result.stdout.strip()) / (1024 ** 3)
        elif caps.is_windows:
            result = subprocess.run(["wmic", "memorychip", "get", "Capacity"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[1:]
                total = sum(int(line.strip()) for line in lines if line.strip().isdigit())
                caps.ram_gb = total / (1024 ** 3)
    except Exception:
        caps.ram_gb = 8.0  # fallback estimate

    # Apple Silicon
    if caps.is_macos:
        proc = platform.processor().lower()
        if any(x in proc for x in ("arm", "m1", "m2", "m3", "m4")):
            caps.is_apple_silicon = True
            caps.has_metal = True

    # NVIDIA CUDA
    nvidia_smi = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
    if nvidia_smi:
        caps.has_cuda = True
        try:
            result = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        caps.gpu_names.append(parts[0])
                        try:
                            mem_str = parts[1].replace(" MiB", "").replace(" MB", "").strip()
                            mem_mib = float(mem_str)
                            caps.vram_gb += mem_mib / 1024
                        except (ValueError, IndexError):
                            pass
                    if len(parts) >= 3:
                        caps.cuda_version = parts[2]
                caps.gpu_count = len(caps.gpu_names)
        except Exception as e:
            logger.debug(f"nvidia-smi query failed: {e}")

    # ROCm
    rocm_smi = shutil.which("rocm-smi") or shutil.which("rocm-smi.exe")
    if rocm_smi or os.environ.get("ROCM_PATH") or os.environ.get("HIP_VISIBLE_DEVICES"):
        caps.has_rocm = True

    # Vulkan
    if shutil.which("vulkaninfo") or shutil.which("vulkaninfo.exe"):
        caps.has_vulkan = True

    # OpenVINO
    try:
        import openvino
        caps.has_openvino = True
    except ImportError:
        pass

    return caps


def estimate_model_capabilities(
    hardware: HardwareCapabilities,
    model_format: str = "gguf",
    runtime_type: str = "llama_cpp",
    context_size: int = 4096,
    model_size_gb: float = 0.0,
) -> ModelCapabilityProfile:
    """Estimate model capabilities based on hardware and model metadata.

    Args:
        hardware: Detected hardware capabilities.
        model_format: Model format (gguf, onnx, safetensors).
        runtime_type: Runtime backend type.
        context_size: Requested context window size.
        model_size_gb: Model file size in GB.

    Returns:
        ModelCapabilityProfile with estimated capabilities.
    """
    profile = ModelCapabilityProfile(
        max_context_length=context_size,
        max_output_tokens=min(context_size // 2, 8192),
        runtime_type=runtime_type,
        model_format=model_format,
        memory_available_gb=hardware.ram_gb,
    )

    # Determine if model fits in available memory
    overhead_factor = 1.3 if runtime_type == "llama_cpp" else 2.0
    if model_size_gb > 0:
        required_gb = model_size_gb * overhead_factor
        available = hardware.ram_gb
        if hardware.vram_gb > 0 and runtime_type in ("llama_cpp", "python_package"):
            available = hardware.vram_gb + (hardware.ram_gb * 0.5)
        profile.max_model_size_gb = available / overhead_factor

    # Estimate tokens/sec based on hardware
    if model_size_gb > 0:
        if hardware.has_cuda and runtime_type != "onnx":
            profile.estimated_tokens_per_sec = min(80.0, 200.0 / max(model_size_gb ** 0.5, 1))
        elif hardware.has_metal:
            profile.estimated_tokens_per_sec = min(60.0, 150.0 / max(model_size_gb ** 0.5, 1))
        elif hardware.has_vulkan:
            profile.estimated_tokens_per_sec = min(50.0, 120.0 / max(model_size_gb ** 0.5, 1))
        else:
            profile.estimated_tokens_per_sec = min(30.0, 60.0 / max(model_size_gb ** 0.5, 1))

    # GPU layers recommendation
    if hardware.vram_gb > 0 and model_size_gb > 0:
        vram_ratio = hardware.vram_gb / model_size_gb
        if vram_ratio >= 1.5:
            profile.recommended_gpu_layers = -1  # all layers
        elif vram_ratio >= 0.8:
            profile.recommended_gpu_layers = int(-1 * vram_ratio)
        else:
            profile.recommended_gpu_layers = int(hardware.vram_gb * 10)
    elif hardware.has_metal or hardware.has_vulkan:
        profile.recommended_gpu_layers = -1
    else:
        profile.recommended_gpu_layers = 0

    # Capability flags based on runtime/model format
    if runtime_type in ("llama_cpp",):
        profile.supports_tool_calling = True
        profile.supports_function_calling = True
        profile.supports_streaming = True
    elif runtime_type == "onnx":
        profile.supports_tool_calling = False
        profile.supports_function_calling = False
    elif runtime_type in ("external_server", "python_package"):
        profile.supports_tool_calling = True
        profile.supports_function_calling = True

    # Batch size recommendation
    if hardware.ram_gb >= 32:
        profile.recommended_batch_size = 1024
    elif hardware.ram_gb >= 16:
        profile.recommended_batch_size = 512
    else:
        profile.recommended_batch_size = 256

    return profile


def get_recommended_runtime(hardware: HardwareCapabilities) -> str:
    """Get the best recommended runtime based on hardware.

    Args:
        hardware: Detected hardware capabilities.

    Returns:
        Runtime backend key string.
    """
    if hardware.has_cuda and hardware.vram_gb >= 8:
        return "cuda"
    if hardware.is_apple_silicon:
        return "metal" if hardware.ram_gb >= 16 else "cpu"
    if hardware.has_rocm:
        return "rocm"
    if hardware.has_vulkan:
        return "vulkan"
    if hardware.is_windows:
        return "onnx"
    return "cpu"
