"""LLM backend — local model engine, provider abstraction, model management."""

from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolDefinition
from nexus_agent.llm.local_engine import LocalEngine
from nexus_agent.llm.model_manager import ModelManager
from nexus_agent.llm.onnx_engine import ONNX_AVAILABLE, OnnxEngine
from nexus_agent.llm.providers.factory import ProviderFactory
from nexus_agent.llm.retry import RetryPolicy, RetryStats, chat_with_retry, with_retry
from nexus_agent.llm.runtime_manager import RuntimeManager

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "Message",
    "ToolCall",
    "ToolDefinition",
    "LocalEngine",
    "ModelManager",
    "OnnxEngine",
    "ONNX_AVAILABLE",
    "RetryPolicy",
    "RetryStats",
    "RuntimeManager",
    "ProviderFactory",
    "chat_with_retry",
    "with_retry",
]

