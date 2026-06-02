from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


TOOL_CALLING_FORMATS = {
    "chatml-function-calling",
    "functionary-v1",
    "functionary-v2",
    "hermes-2-pro",
    "mistral-instruct",
    "llama-3-tool",
    "command-r",
}

MODEL_FORMAT_MAP = {
    "hermes": "chatml-function-calling",
    "functionary": "functionary-v2",
    "mistral": "mistral-instruct",
    "qwen": "chatml-function-calling",
    "llama-3": "llama-3-tool",
    "command-r": "command-r",
    "deepseek": "chatml-function-calling",
    "mythos": "chatml-function-calling",
}


def _detect_chat_format(model_path: str) -> str:
    name = Path(model_path).stem.lower()
    for pattern, fmt in MODEL_FORMAT_MAP.items():
        if pattern in name:
            return fmt
    return "chatml-function-calling"


def _detect_gpu_support() -> dict[str, Any]:
    info: dict[str, Any] = {"available": False, "backend": None, "layers_recommended": 0}
    try:
        import psutil
        psutil.virtual_memory().total / (1024**3)
    except ImportError:
        pass

    try:
        cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if cuda_visible != "-1":
            try:
                from llama_cpp import llama_supports_gpu_offload
                if llama_supports_gpu_offload():
                    info["available"] = True
                    info["backend"] = "cuda"
                    info["layers_recommended"] = -1
                    return info
            except (ImportError, AttributeError):
                pass
    except (ImportError, AttributeError, OSError):
        pass

    if platform.system() == "Darwin":
        try:
            from llama_cpp import llama_supports_gpu_offload
            if llama_supports_gpu_offload():
                info["available"] = True
                info["backend"] = "metal"
                info["layers_recommended"] = -1
                return info
        except (ImportError, AttributeError):
            pass

    info["backend"] = "cpu"
    info["layers_recommended"] = 0
    return info
