"""
Model Manager — GGUF model discovery, metadata, and hardware detection.

Scans configured directories for GGUF files, extracts metadata,
detects hardware capabilities, and recommends appropriate model sizes.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Simple TTL cache for expensive operations
_TTL_CACHE: dict[str, tuple[float, Any]] = {}
_TTL_DEFAULT = 300.0  # 5 minutes


def _ttl_get(key: str, ttl: float = _TTL_DEFAULT) -> Any | None:
    """Get a cached value if still valid."""
    entry = _TTL_CACHE.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None


def _ttl_set(key: str, value: Any) -> None:
    """Set a cached value with current timestamp."""
    _TTL_CACHE[key] = (time.monotonic(), value)


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    remaining = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if remaining < 1024:
            return f"{remaining:.1f} {unit}"
        remaining /= 1024
    return f"{remaining:.1f} PB"


def _guess_quantization(filename: str) -> str:
    """Guess quantization type from filename."""
    name = filename.upper()
    quant_types = sorted([
        "Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L",
        "Q4_0", "Q4_1", "Q4_K_S", "Q4_K_M",
        "Q5_0", "Q5_1", "Q5_K_S", "Q5_K_M",
        "Q6_K", "Q8_0", "F16", "F32",
        "IQ1_S", "IQ1_M", "IQ2_XXS", "IQ2_XS", "IQ2_S", "IQ2_M",
        "IQ3_XXS", "IQ3_XS", "IQ3_S", "IQ4_XS", "IQ4_NL",
    ], key=len, reverse=True)
    for qt in quant_types:
        if qt in name or qt.replace("_", "-") in name:
            return qt
    return "unknown"


def _guess_param_count(filename: str) -> str:
    """Guess parameter count from filename."""
    name = filename.lower()
    # Common patterns: 7b, 13b, 70b, 1.5b, etc.
    match = re.search(r'(\d+\.?\d*)[_-]?b(?:illion)?', name)
    if match:
        return f"{match.group(1)}B"
    return "unknown"


class ModelManager:
    """Manages GGUF model discovery, metadata, and hardware recommendations."""

    def __init__(self, models_dir: str | None = None):
        """Initialize the model manager.

        Args:
            models_dir: Directory to scan for GGUF models.
                        Defaults to ~/models or NEXUS_MODELS_DIR env var.
        """
        if models_dir:
            self._models_dir = Path(models_dir).expanduser().resolve()
        else:
            env_dir = os.environ.get("NEXUS_MODELS_DIR", "~/models")
            self._models_dir = Path(env_dir).expanduser().resolve()
        logger.info(f"ModelManager initialized with models directory: {self._models_dir}")

    @property
    def models_dir(self) -> Path:
        """Get the models directory (returns a copy to avoid mutation)."""
        return Path(self._models_dir)

    def discover_models(self, search_dirs: list[str] | None = None) -> list[dict[str, Any]]:
        """Discover GGUF models in configured directories.

        Args:
            search_dirs: Additional directories to search.

        Returns:
            List of model info dicts sorted by name.
        """
        cache_key = f"discover:{self._models_dir}:{tuple(search_dirs or [])}"
        cached = _ttl_get(cache_key)
        if cached is not None:
            return cached

        models: list[dict[str, Any]] = []
        dirs_to_search = [self._models_dir]

        if search_dirs:
            dirs_to_search.extend(Path(d).expanduser().resolve() for d in search_dirs)

        for search_dir in dirs_to_search:
            if not search_dir.exists():
                logger.debug(f"Models directory does not exist: {search_dir}")
                continue

            # Scan for .gguf files
            for gguf_file in search_dir.rglob("*.gguf"):
                try:
                    stat = gguf_file.stat()
                    model_info = {
                        "name": gguf_file.stem,
                        "filename": gguf_file.name,
                        "path": str(gguf_file),
                        "size_bytes": stat.st_size,
                        "size_str": _format_size(stat.st_size),
                        "quantization": _guess_quantization(gguf_file.name),
                        "param_count": _guess_param_count(gguf_file.name),
                        "modified": stat.st_mtime,
                        "format": "gguf",
                    }
                    models.append(model_info)
                except OSError as e:
                    logger.warning(f"Could not read model file {gguf_file}: {e}")

            # Scan for ONNX GenAI model folders (folders containing genai_config.json)
            for config_file in search_dir.rglob("genai_config.json"):
                try:
                    model_dir = config_file.parent
                    stat = config_file.stat()
                    # Calculate directory size (recursive)
                    total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                    model_info = {
                        "name": model_dir.name,
                        "filename": model_dir.name,
                        "path": str(model_dir),
                        "size_bytes": total_size,
                        "size_str": _format_size(total_size),
                        "quantization": "ONNX",
                        "param_count": _guess_param_count(model_dir.name),
                        "modified": stat.st_mtime,
                        "format": "onnx",
                    }
                    models.append(model_info)
                except OSError as e:
                    logger.warning(f"Could not read ONNX model directory {config_file.parent}: {e}")

        # Sort by name
        models.sort(key=lambda m: m["name"].lower())

        _ttl_set(cache_key, models)
        return models

    def get_model_info(self, model_path: str) -> dict[str, Any] | None:
        """Get detailed info about a specific GGUF model.

        Attempts to read GGUF metadata for accurate information.
        """
        path = Path(model_path).resolve()
        if not path.exists():
            return None

        info: dict[str, Any] = {
            "name": path.stem,
            "filename": path.name,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "size_str": _format_size(path.stat().st_size),
            "quantization": _guess_quantization(path.name),
            "param_count": _guess_param_count(path.name),
        }

        # Try to read GGUF metadata
        try:
            info.update(self._read_gguf_metadata(path))
        except (OSError, ValueError) as e:
            logger.debug(f"Could not read GGUF metadata: {e}")

        return info

    def _read_gguf_metadata(self, path: Path) -> dict[str, Any]:
        """Read metadata from a GGUF file header using struct-based parsing.

        GGUF files contain key-value metadata in their header that
        includes model architecture, context length, etc.
        This avoids loading the full model into memory.
        """
        metadata: dict[str, Any] = {}

        try:
            # Try GGUF reader from llama-cpp-python first
            try:
                from gguf import GGUFReader
                reader = GGUFReader(str(path))
                metadata["vocab_size"] = reader.fields.get("tokenizer.ggml.vocab_size", None)
                if metadata["vocab_size"] is None:
                    metadata["vocab_size"] = reader.fields.get("tokenizer.ggml.vocab_size", None)
                metadata["max_context"] = self._context_size  # GGUF doesn't encode context directly
                metadata["architecture"] = str(reader.fields.get("general.architecture", b""))
                return metadata
            except ImportError:
                pass

            # Fallback: read GGUF header directly with struct
            import struct
            GGUF_MAGIC = 0x46554747  # "GGUF" in little-endian
            with open(path, "rb") as f:
                magic = struct.unpack("<I", f.read(4))[0]
                if magic != GGUF_MAGIC:
                    logger.debug(f"Not a valid GGUF file: {path}")
                    return metadata

                version = struct.unpack("<I", f.read(4))[0]
                tensor_count = struct.unpack("<Q", f.read(8))[0]
                metadata_kv_count = struct.unpack("<Q", f.read(8))[0]

                # Read key-value metadata
                for _ in range(metadata_kv_count):
                    try:
                        key_len = struct.unpack("<Q", f.read(8))[0]
                        key = f.read(key_len).decode("utf-8", errors="replace")
                        val_type = struct.unpack("<I", f.read(4))[0]
                        # GGUF value types: 0=uint8, 1=int8, 2=uint16, 3=int16, 4=uint32, 5=int32, 6=float32, 7=bool, 8=string, 9-11=arrays
                        if val_type == 8:  # string
                            val_len = struct.unpack("<Q", f.read(8))[0]
                            val = f.read(val_len).decode("utf-8", errors="replace")
                            metadata[key] = val
                        elif val_type in (4, 5):  # uint32/int32
                            val = struct.unpack("<i", f.read(4))[0]
                            metadata[key] = val
                        elif val_type == 6:  # float32
                            val = struct.unpack("<f", f.read(4))[0]
                            metadata[key] = val
                        elif val_type == 7:  # bool
                            val = struct.unpack("<?", f.read(1))[0]
                            metadata[key] = val
                        elif val_type == 0:  # uint8
                            val = struct.unpack("<B", f.read(1))[0]
                            metadata[key] = val
                        elif val_type == 2:  # uint16
                            val = struct.unpack("<H", f.read(2))[0]
                            metadata[key] = val
                        elif val_type == 3:  # int16
                            val = struct.unpack("<h", f.read(2))[0]
                            metadata[key] = val
                        elif val_type == 1:  # int8
                            val = struct.unpack("<b", f.read(1))[0]
                            metadata[key] = val
                        # Skip array types and unknown types
                    except (ValueError, TypeError, KeyError):
                        break

        except ImportError:
            logger.debug("GGUF reading libraries not available")
        except (OSError, ValueError) as e:
            logger.debug(f"Quick metadata read failed: {e}")

        return metadata

    def detect_hardware(self) -> dict[str, Any]:
        """Detect hardware capabilities for model hosting.

        Returns detailed info about CPU, RAM, GPU, and
        recommended maximum model size.
        """
        cache_key = "detect_hardware"
        cached = _ttl_get(cache_key)
        if cached is not None:
            return cached

        hw: dict[str, Any] = {}

        # CPU info
        hw["cpu"] = platform.processor() or platform.machine()
        hw["cpu_threads"] = os.cpu_count() or 1
        hw["platform"] = platform.system()
        hw["architecture"] = platform.machine()

        # RAM info
        try:
            import psutil
            vm = psutil.virtual_memory()
            hw["ram_total"] = _format_size(vm.total)
            hw["ram_available"] = _format_size(vm.available)
            hw["ram_total_bytes"] = vm.total
            hw["ram_available_bytes"] = vm.available
        except ImportError:
            hw["ram_total"] = "unknown (install psutil)"
            hw["ram_available"] = "unknown"
            hw["ram_total_bytes"] = 0

        # GPU detection
        hw["gpu"] = "Not detected"
        hw["vram"] = "N/A"

        # Try NVIDIA GPU
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                gpu_name, vram_mb = lines[0].split(", ")
                hw["gpu"] = gpu_name.strip()
                hw["vram"] = f"{int(vram_mb.strip())} MB"
                hw["vram_bytes"] = int(vram_mb.strip()) * 1024 * 1024
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        # macOS Metal
        if platform.system() == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5,
                )
                if "Metal" in result.stdout:
                    hw["gpu"] = "Apple Metal (integrated)"
                    # Apple Silicon shares system RAM
                    hw["vram"] = "Shared with system RAM"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # NPU detection (Windows first-class, Linux fallback)
        hw["npu"] = "Not detected"
        if platform.system() == "Windows":
            try:
                import subprocess
                # Run PowerShell query for NPUs (Qualcomm, Intel AI Boost, AMD IPU, etc.)
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_PnPSignedDevice | "
                    "Where-Object { $_.FriendlyName -like '*NPU*' -or $_.FriendlyName -like '*Neural*' -or $_.FriendlyName -like '*Intel AI Boost*' -or $_.FriendlyName -like '*Hexagon*' } | "
                    "Select-Object -ExpandProperty FriendlyName"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    npu_names = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
                    if npu_names:
                        hw["npu"] = npu_names[0]
            except (OSError, AttributeError):
                pass
        elif platform.system() == "Linux":
            # Check for /sys/class/accel (Linux accelerator subsystem used for NPUs)
            accel_path = Path("/sys/class/accel")
            if accel_path.exists():
                try:
                    devices = list(accel_path.glob("accel*"))
                    if devices:
                        hw["npu"] = f"Detected ({len(devices)} device(s) in /sys/class/accel)"
                except (NotADirectoryError, FileNotFoundError, PermissionError):
                    pass

        # Recommend model size
        ram_bytes = hw.get("ram_total_bytes", 0)
        vram_bytes = hw.get("vram_bytes", 0)

        usable_memory = max(ram_bytes, vram_bytes)
        if usable_memory >= 64 * 1024**3:
            hw["recommended_model_size"] = "70B+ (Q4 quantization)"
        elif usable_memory >= 32 * 1024**3:
            hw["recommended_model_size"] = "30B-70B (Q4-Q5 quantization)"
        elif usable_memory >= 16 * 1024**3:
            hw["recommended_model_size"] = "13B-30B (Q4-Q5 quantization)"
        elif usable_memory >= 8 * 1024**3:
            hw["recommended_model_size"] = "7B-13B (Q4 quantization)"
        elif usable_memory >= 4 * 1024**3:
            hw["recommended_model_size"] = "3B-7B (Q2-Q4 quantization)"
        else:
            hw["recommended_model_size"] = "1B-3B (Q2-Q3 quantization) — limited resources"

        _ttl_set(cache_key, hw)
        return hw

    def find_best_model(self) -> Path | None:
        """Auto-detect the best available model based on hardware.

        Prefers models that:
        1. Fit in available RAM/VRAM
        2. Have higher quantization quality (Q5 > Q4 > Q3)
        3. Have more parameters (70B > 13B > 7B)
        """
        models = self.discover_models()
        if not models:
            return None

        hw = self.detect_hardware()
        ram_available = hw.get("ram_available_bytes", 0)
        vram_available = hw.get("vram_bytes", 0)

        usable_memory = max(ram_available, vram_available) if vram_available > 0 else ram_available

        # Filter to models that fit in available memory (with 2GB headroom)
        headroom = 2 * 1024**3
        fitting_models = [
            m for m in models
            if m["size_bytes"] < (usable_memory - headroom)
        ]

        if not fitting_models:
            # Fall back to smallest model
            models.sort(key=lambda m: m["size_bytes"])
            return models[0]["path"]

        # Score models: prefer larger, higher quality
        quant_scores = {
            "F32": 10, "F16": 9, "Q8_0": 8, "Q6_K": 7,
            "Q5_K_M": 6, "Q5_K_S": 5, "Q5_1": 5, "Q5_0": 5,
            "Q4_K_M": 4, "Q4_K_S": 3, "Q4_1": 3, "Q4_0": 3,
            "Q3_K_L": 2, "Q3_K_M": 2, "Q3_K_S": 1,
            "Q2_K": 0, "unknown": 3,
        }

        def score_model(m: dict[str, Any]) -> float:
            q_score = quant_scores.get(m.get("quantization", "unknown"), 3)
            size_gb = m["size_bytes"] / (1024**3)  # Size in GB
            # Balanced score: weight model quantization quality appropriately against size
            return (q_score * 15.0) + (size_gb * 2.0)

        fitting_models.sort(key=score_model, reverse=True)
        return fitting_models[0]["path"]

    def evaluate_loading_guardrail(self, model_path: str, guardrail_level: str = "balanced") -> dict[str, Any]:
        """Evaluate memory requirements of a model against available system RAM/VRAM.

        Args:
            model_path: Path to the GGUF model file or ONNX model folder.
            guardrail_level: Guardrail safety level (off, relaxed, balanced, strict).

        Returns:
            Dict containing {"allowed": bool, "warning": str | None}
        """
        level = guardrail_level.lower().strip()
        if level == "off":
            return {"allowed": True, "warning": None}

        path = Path(model_path).resolve()
        if not path.exists():
            return {"allowed": False, "warning": "Model file/folder does not exist."}

        # Calculate model size
        model_size = 0
        if path.is_file():
            model_size = path.stat().st_size
        else:
            model_size = sum(f.stat().st_size for f in path.glob("*") if f.is_file())

        hw = self.detect_hardware()
        ram_available = hw.get("ram_available_bytes", 0)
        ram_total = hw.get("ram_total_bytes", 0)
        vram_bytes = hw.get("vram_bytes", 0)

        # Usable physical headroom
        limit_pct = 0.85
        if level == "strict":
            limit_pct = 0.70
        elif level == "relaxed":
            limit_pct = 0.95

        # Strict memory limit check
        max_allowed_bytes = int(ram_total * limit_pct)
        if vram_bytes > 0:
            max_allowed_bytes = int((vram_bytes + ram_total) * limit_pct)

        logger.info(f"Guardrail check: model_size={_format_size(model_size)}, max_allowed={_format_size(max_allowed_bytes)}")

        if model_size > max_allowed_bytes:
            msg = (
                f"Model size ({_format_size(model_size)}) exceeds the {level} guardrail limit "
                f"({int(limit_pct * 100)}% of memory budget: {_format_size(max_allowed_bytes)}). "
                f"Loading this model might crash your machine or cause severe system lag."
            )
            if level == "strict":
                return {"allowed": False, "warning": msg}
            else:
                return {"allowed": True, "warning": f"⚠️ WARNING: {msg}"}

        return {"allowed": True, "warning": None}

