"""
ONNX Runtime GenAI Engine — Local NPU-accelerated inference.

Allows running ONNX-format models on local hardware with direct acceleration
for Windows NPUs (via DirectML/WinML), as well as CPU and GPU fallback.

Standardizes interactions to implement the unified LLMProvider interface.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from nexus_agent.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ProviderCapabilities,
    Role,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

# Try to import onnxruntime_genai
try:
    import onnxruntime_genai as og
    ONNX_AVAILABLE = True
except ImportError:
    og = None
    ONNX_AVAILABLE = False


class OnnxEngine(LLMProvider):
    """Local LLM engine using ONNX Runtime GenAI.

    Designed for Windows NPU (DirectML) offloading and optimized ONNX inference.
    """

    def __init__(
        self,
        model_path: str | None = None,
        context_size: int = 4096,
        gpu_backend: str = "auto",  # auto, cpu, dml, cuda
        verbose: bool = False,
    ):
        """Initialize the ONNX engine.

        Args:
            model_path: Path to the ONNX model directory.
            context_size: Context window size.
            gpu_backend: Execution provider backend (auto, cpu, dml, cuda).
            verbose: Enable verbose logging.
        """
        self._model_path = model_path
        self._context_size = context_size
        self._gpu_backend = gpu_backend.lower()
        self._verbose = verbose

        self._model = None
        self._tokenizer = None
        self._model_name_str = ""

        if model_path:
            self.load_model(model_path)

    @property
    def name(self) -> str:
        return "onnx"

    @property
    def model_name(self) -> str:
        return self._model_name_str or "no-model-loaded"

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get capabilities of the ONNX engine."""
        return ProviderCapabilities(
            supports_tool_calling=True,  # Supported via JSON-based tool instruction emulation
            supports_vision=False,
            supports_streaming=True,
            supports_system_message=True,
            supports_parallel_tool_calls=False,
            max_context_length=self._context_size,
            max_output_tokens=self._context_size // 2,
        )

    def load_model(self, model_path: str) -> None:
        """Load an ONNX model directory."""
        if not ONNX_AVAILABLE:
            raise RuntimeError(
                "onnxruntime-genai is not installed. Install it via pip install onnxruntime-genai"
            )

        model_dir = Path(model_path).resolve()
        if not model_dir.exists():
            raise FileNotFoundError(f"ONNX model directory not found: {model_dir}")

        if not model_dir.is_dir():
            raise ValueError(f"Expected model directory, got file: {model_dir}")

        # Unload previous model if loaded
        self.unload_model()

        logger.info(f"Loading ONNX model from {model_dir.name} (backend={self._gpu_backend})")

        try:
            # Set backend options (DML is default for NPU/GPU on Windows, CUDA for Nvidia)
            # og.Model takes a directory path and automatically resolves configuration.
            self._model = og.Model(str(model_dir))
            self._tokenizer = og.Tokenizer(self._model)
            self._model_path = str(model_dir)
            self._model_name_str = model_dir.name
            logger.info(f"ONNX model loaded successfully: {self._model_name_str}")
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self.unload_model()
            raise RuntimeError(f"Failed to load ONNX model: {e}") from e

    def unload_model(self) -> None:
        """Unload ONNX model and tokenizer."""
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        self._model_name_str = ""
        logger.info("ONNX model unloaded")

    def _ensure_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError("No ONNX model loaded. Call load_model() first.")

    def _format_prompt(self, messages: list[Message], tools: list[ToolDefinition] | None = None) -> str:
        """Format message conversation list into standard ChatML or Instruct prompt text.

        Injects tool definitions and formatting rules if tools are present.
        """
        prompt = ""

        # Inject tool schemas in system prompt if they are available
        system_content = ""
        tool_system_prompt = ""

        if tools:
            tool_schemas = [t.to_openai_format()["function"] for t in tools]
            tool_system_prompt = (
                "\n\nYou have access to the following tools:\n"
                f"{json.dumps(tool_schemas, indent=2)}\n\n"
                "To call a tool, reply with a JSON object in this format:\n"
                "```json\n"
                "{\n"
                '  "name": "tool_name",\n'
                '  "arguments": {\n'
                '    "arg_name": "arg_value"\n'
                "  }\n"
                "}\n"
                "```\n"
                "Make sure to specify valid arguments matching the tool schema."
            )

        for msg in messages:
            role = msg.role.value
            content = msg.content or ""

            if msg.role == Role.SYSTEM:
                system_content += content
            elif msg.role == Role.TOOL:
                prompt += f"<|im_start|>user\n[TOOL RESULT for {msg.name or 'tool'} (ID: {msg.tool_call_id or ''})]:\n{content}<|im_end|>\n"
            else:
                prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"

        # Prefix system prompt
        if system_content or tool_system_prompt:
            prompt = f"<|im_start|>system\n{system_content}{tool_system_prompt}<|im_end|>\n" + prompt

        # Append assistant trigger
        prompt += "<|im_start|>assistant\n"
        return prompt

    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        self._ensure_loaded()
        prompt = self._format_prompt(messages, tools)

        # Tokenize and create generator parameters
        if self._tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")
        input_tokens = self._tokenizer.encode(prompt)
        params = og.GeneratorParams(self._model)
        params.input_ids = input_tokens

        # Set inference options
        max_tokens = min(max_tokens, self._context_size - len(input_tokens))
        max_len = min(max_tokens + len(input_tokens), self._context_size)
        params.set_search_options(
            max_length=max_len,
            temperature=temperature,
            top_k=kwargs.get("top_k", 40),
            top_p=kwargs.get("top_p", 0.9),
        )

        generator = None
        steps = 0
        try:
            generator = og.Generator(self._model, params)
            tokens: list[int] = []
            while not generator.is_done() and steps < 10000:
                generator.compute_logits()
                generator.generate_next_token()
                tokens.append(generator.get_next_tokens()[0])
                steps += 1

            output_text = self._tokenizer.decode(tokens)

            # Post-process response to parse tool calls
            content, tool_calls = self._parse_emulated_tool_calls(output_text)

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason="stop" if not tool_calls else "tool_calls",
                usage={
                    "prompt_tokens": len(input_tokens),
                    "completion_tokens": len(tokens),
                    "total_tokens": len(input_tokens) + len(tokens),
                },
                model=self._model_name_str,
            )
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"ONNX model inference failed: {e}")
            raise RuntimeError(f"ONNX model inference failed: {e}") from e
        finally:
            if generator is not None:
                del generator

    def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Streaming chat completion."""
        self._ensure_loaded()
        prompt = self._format_prompt(messages, tools)

        # Tokenize and create generator parameters
        if self._tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")
        input_tokens = self._tokenizer.encode(prompt)
        params = og.GeneratorParams(self._model)
        params.input_ids = input_tokens

        max_tokens = min(max_tokens, self._context_size - len(input_tokens))
        max_len = min(max_tokens + len(input_tokens), self._context_size)
        params.set_search_options(
            max_length=max_len,
            temperature=temperature,
            top_k=kwargs.get("top_k", 40),
            top_p=kwargs.get("top_p", 0.9),
        )

        generator = None
        tokenizer_stream = None
        steps = 0
        try:
            generator = og.Generator(self._model, params)
            tokenizer_stream = self._tokenizer.create_stream()

            full_text = ""
            while not generator.is_done() and steps < 10000:
                generator.compute_logits()
                generator.generate_next_token()
                next_token = generator.get_next_tokens()[0]
                steps += 1

                text_chunk = tokenizer_stream.decode(next_token)
                full_text += text_chunk

                # If the assistant is starting to output a JSON tool call block, we should accumulate
                # and check if we are yielding content or a tool call chunk.
                yield StreamChunk(
                    content=text_chunk,
                    is_final=False,
                )

            # Check if there are tool calls in the final accumulated text
            content, tool_calls = self._parse_emulated_tool_calls(full_text)
            if tool_calls:
                yield StreamChunk(
                    tool_calls=tool_calls,
                    finish_reason="tool_calls",
                    is_final=True,
                )
            else:
                yield StreamChunk(
                    finish_reason="stop",
                    is_final=True,
                )
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"ONNX streaming failed: {e}")
            raise RuntimeError(f"ONNX streaming failed: {e}") from e
        finally:
            if tokenizer_stream is not None:
                del tokenizer_stream
            if generator is not None:
                del generator

    def _parse_emulated_tool_calls(self, text: str) -> tuple[str | None, list[ToolCall] | None]:
        """Parse emulated JSON tool call block from model output text.

        Allows standard ONNX text-based models to invoke tool calls.
        """
        # Look for markdown JSON block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if not match:
            return text, None

        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                tool_call = ToolCall(
                    id=f"onnx_call_{uuid.uuid4().hex[:8]}",
                    name=data["name"],
                    arguments=data["arguments"],
                )

                # Split content before the code block using match position
                content_before = text[:match.start()].strip()
                return content_before or None, [tool_call]
            elif isinstance(data, list):
                logger.warning("Tool call returned as array format; expected single object")
        except json.JSONDecodeError:
            pass

        return text, None

    def get_available_models(self) -> list[dict[str, Any]]:
        """List current loaded ONNX model."""
        if self._model_path:
            return [{
                "id": self._model_name_str,
                "name": self._model_name_str,
                "path": self._model_path,
                "provider": "onnx",
            }]
        return []

    def count_tokens(self, text: str) -> int:
        """Count tokens using ONNX tokenizer."""
        if self._tokenizer is not None:
            try:
                return len(self._tokenizer.encode(text))
            except (ValueError, RuntimeError):
                pass
        return len(text) // 4

    def validate_config(self) -> list[str]:
        """Validate config."""
        errors = []
        if self._model_path:
            path = Path(self._model_path)
            if not path.exists():
                errors.append(f"ONNX model directory not found: {path}")
            elif not path.is_dir():
                errors.append(f"ONNX path must be a directory: {path}")
        return errors

    def close(self) -> None:
        self.unload_model()
