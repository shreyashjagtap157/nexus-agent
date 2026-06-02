from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from nexus_agent.llm.base import (
    LLMProvider,
    ProviderCapabilities,
)
from nexus_agent.llm.local_engine.inference_mixin import InferenceMixin
from nexus_agent.llm.local_engine.protocol_mixin import ProtocolMixin
from nexus_agent.llm.local_engine.utils import (
    TOOL_CALLING_FORMATS,
    _detect_chat_format,
    _detect_gpu_support,
)
from nexus_agent.protocol.agent_protocol import (
    AgentProtocol,
    AgentRole,
)

logger = logging.getLogger(__name__)


class LocalEngine(ProtocolMixin, InferenceMixin, LLMProvider):
    """
    Local LLM engine using llama-cpp-python with optional agent protocol support.

    When use_agent_protocol=True, the engine:
    - Accepts structured agent goals instead of raw messages
    - Formats inputs as XML using AgentInputSerializer
    - Parses outputs as JSON using AgentOutputParser
    - Supports file operations, commands, tool calls, and multi-agent coordination
    - Logs all execution events to an immutable event log
    """

    def __init__(
        self,
        model_path: str | None = None,
        gpu_layers: int = -1,
        context_size: int = 4096,
        threads: int | None = None,
        chat_format: str = "auto",
        batch_size: int = 512,
        use_mmap: bool = True,
        use_mlock: bool = False,
        seed: int = -1,
        verbose: bool = False,
        gpu_backend: str = "auto",
        flash_attention: bool = True,
        unified_kv_cache: bool = True,
        rope_freq_base: float = 0.0,
        rope_freq_scale: float = 0.0,
        kv_quant_type: str = "f16",
        keep_in_memory: bool = True,
        use_agent_protocol: bool = False,
        agent_role: AgentRole = AgentRole.GENERAL,
        reasoning_depth: int = 8,
    ):
        self._model_path = model_path
        self._gpu_layers = gpu_layers
        self._context_size = context_size
        self._threads = threads if threads is not None else (os.cpu_count() or 4)
        self._chat_format = chat_format
        self._batch_size = batch_size
        self._use_mmap = use_mmap
        self._use_mlock = use_mlock
        self._seed = seed
        self._verbose = verbose
        self._gpu_backend = gpu_backend.lower()
        self._flash_attention = flash_attention
        self._unified_kv_cache = unified_kv_cache
        self._rope_freq_base = rope_freq_base
        self._rope_freq_scale = rope_freq_scale
        self._kv_quant_type = kv_quant_type
        self._keep_in_memory = keep_in_memory

        self._use_agent_protocol = use_agent_protocol
        self._agent_role = agent_role
        self._reasoning_depth = reasoning_depth

        self._llm = None
        self._model_name_str = ""
        self._gpu_info = _detect_gpu_support()
        self._loading_error = None

        self._protocol: AgentProtocol | None = None
        self._current_goal: str = ""
        self._tasks: list[Any] = []
        self._tool_results: dict[str, Any] = {}

        if model_path:
            self.load_model(model_path)

    @property
    def name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name_str or "no-model-loaded"

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None and self._loading_error is None

    @property
    def model_path(self) -> str | None:
        return self._model_path

    @property
    def agent_protocol(self) -> AgentProtocol | None:
        return self._protocol

    def get_capabilities(self) -> ProviderCapabilities:
        chat_fmt = self._chat_format
        supports_tools = chat_fmt in TOOL_CALLING_FORMATS or chat_fmt == "auto"

        return ProviderCapabilities(
            supports_tool_calling=supports_tools,
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=self._context_size,
            max_output_tokens=self._context_size // 2,
        )

    def load_model(self, model_path: str) -> None:
        from llama_cpp import Llama

        model_file = Path(model_path).resolve()
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        if not model_file.suffix.lower() == ".gguf":
            raise ValueError(f"Expected .gguf file, got: {model_file.suffix}")

        self.unload_model()

        chat_format = self._chat_format
        if chat_format == "auto":
            chat_format = _detect_chat_format(str(model_file))

        gpu_layers = self._gpu_layers
        if self._gpu_backend == "cpu":
            gpu_layers = 0
            logger.info("Explicitly configured CPU-only backend")
        elif gpu_layers == -1:
            if self._gpu_backend != "auto":
                gpu_layers = -1
                logger.info(f"Using forced GPU backend: {self._gpu_backend}")
            elif not self._gpu_info.get("available", False):
                gpu_layers = 0
                logger.info("No GPU detected, falling back to CPU-only inference")

        logger.info(
            f"Loading model: {model_file.name} "
            f"(gpu_layers={gpu_layers}, ctx={self._context_size}, "
            f"chat_format={chat_format})"
        )

        import llama_cpp
        kv_type = llama_cpp.GGML_TYPE_F16
        if self._kv_quant_type == "q8_0":
            kv_type = getattr(llama_cpp, "GGML_TYPE_Q8_0", kv_type)
        elif self._kv_quant_type == "q4_0":
            kv_type = getattr(llama_cpp, "GGML_TYPE_Q4_0", kv_type)
        elif self._kv_quant_type.lower() != "f16":
            logger.warning(f"Unrecognized kv_quant_type '{self._kv_quant_type}', falling back to f16")

        extra_args: dict[str, Any] = {}
        if self._rope_freq_base > 0:
            extra_args["rope_freq_base"] = self._rope_freq_base
        if self._rope_freq_scale > 0:
            extra_args["rope_freq_scale"] = self._rope_freq_scale

        try:
            self._loading_error = None
            self._llm = Llama(
                model_path=str(model_file),
                n_gpu_layers=gpu_layers,
                n_ctx=self._context_size,
                n_threads=self._threads,
                n_batch=self._batch_size,
                use_mmap=self._use_mmap,
                use_mlock=self._use_mlock,
                seed=self._seed,
                chat_format=chat_format,
                verbose=self._verbose,
                flash_attn=self._flash_attention,
                type_k=kv_type,
                type_v=kv_type,
                **extra_args,
            )
        except (ValueError, RuntimeError, OSError, MemoryError) as e:
            logger.error(f"Failed to instantiate Llama engine: {e}")
            self._loading_error = e
            self.unload_model()
            raise RuntimeError(f"Failed to load local model: {e}") from e

        self._model_path = str(model_file)
        self._model_name_str = model_file.stem
        self._chat_format = chat_format

        logger.info(f"Model loaded successfully: {self._model_name_str}")

    def unload_model(self) -> None:
        if self._llm is not None:
            try:
                if hasattr(self._llm, "close"):
                    self._llm.close()
                elif hasattr(self._llm, "reset"):
                    self._llm.reset()
            except (AttributeError, RuntimeError) as e:
                logger.warning(f"Error during explicit Llama resource release: {e}")

            del self._llm
            self._llm = None
            self._model_name_str = ""
            import gc
            gc.collect()
            logger.info("Model unloaded")

    def _ensure_loaded(self) -> None:
        if self._llm is None:
            raise RuntimeError(
                "No model loaded. Call load_model() first or pass model_path to constructor."
            )

    def get_available_models(self) -> list[dict[str, Any]]:
        if self._model_path:
            return [{
                "id": self._model_name_str,
                "name": self._model_name_str,
                "path": self._model_path,
                "provider": "local",
                "supports_agent_protocol": True,
            }]
        return []

    def count_tokens(self, text: str) -> int:
        if self._llm is not None:
            try:
                tokens = self._llm.tokenize(text.encode("utf-8"))
                return len(tokens)
            except (UnicodeEncodeError, RuntimeError, ValueError) as e:
                logger.debug(f"Token count using model failed: {e}")
        words = text.split()
        if not words:
            return 0
        return max(1, int(len(words) * 1.33))

    def validate_config(self) -> list[str]:
        errors = []
        if self._model_path:
            path = Path(self._model_path)
            if not path.exists():
                errors.append(f"Model file not found: {path}")
            elif not path.suffix.lower() == ".gguf":
                errors.append(f"Model file must be .gguf format: {path}")
        if self._context_size < 512:
            errors.append(f"Context size too small: {self._context_size} (min 512)")
        if self._threads < 0:
            errors.append(f"Thread count must be >= 0: {self._threads}")
        return errors

    def get_model_info(self) -> dict[str, Any]:
        if not self.is_loaded:
            return {"status": "no model loaded"}

        info = {
            "name": self._model_name_str,
            "path": self._model_path,
            "context_size": self._context_size,
            "gpu_layers": self._gpu_layers,
            "gpu_backend": self._gpu_info.get("backend", "cpu"),
            "threads": self._threads,
            "chat_format": self._chat_format,
            "batch_size": self._batch_size,
            "agent_protocol_enabled": self._use_agent_protocol,
        }

        if self._llm:
            try:
                info["vocab_size"] = self._llm.n_vocab()
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to get vocab size: {e}")
            try:
                info["context_length"] = self._llm.n_ctx()
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to get context length: {e}")

        return info

    def get_event_log(self) -> str:
        if self._protocol:
            return self._protocol.event_logger.to_jsonl()
        return ""

    def close(self) -> None:
        self.unload_model()
        self._protocol = None
