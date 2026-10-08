"""Extensible provider catalog with OpenAI-compatible provider metadata."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    name: str
    protocol: str
    base_url: str | None
    env_key: str | None
    supports_custom_models: bool = True


# Common providers are descriptors rather than hardcoded model lists. Model
# availability can therefore change without requiring a NexusAgent release.
PROVIDERS = {
    "openai": ProviderDescriptor("openai", "OpenAI", "openai", "https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "anthropic": ProviderDescriptor("anthropic", "Anthropic", "anthropic", None, "ANTHROPIC_API_KEY"),
    "google": ProviderDescriptor("google", "Google Gemini", "gemini", None, "GOOGLE_API_KEY"),
    "xai": ProviderDescriptor("xai", "xAI", "openai_compatible", "https://api.x.ai/v1/chat/completions", "XAI_API_KEY"),
    "mistral": ProviderDescriptor("mistral", "Mistral AI", "openai_compatible", "https://api.mistral.ai/v1/chat/completions", "MISTRAL_API_KEY"),
    "groq": ProviderDescriptor("groq", "Groq", "openai_compatible", "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "together": ProviderDescriptor("together", "Together AI", "openai_compatible", "https://api.together.xyz/v1/chat/completions", "TOGETHERAI_API_KEY"),
    "fireworks": ProviderDescriptor("fireworks", "Fireworks AI", "openai_compatible", "https://api.fireworks.ai/inference/v1/chat/completions", "FIREWORKS_API_KEY"),
    "deepinfra": ProviderDescriptor("deepinfra", "DeepInfra", "openai_compatible", "https://api.deepinfra.com/v1/openai/chat/completions", "DEEPINFRA_API_KEY"),
    "cerebras": ProviderDescriptor("cerebras", "Cerebras", "openai_compatible", "https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY"),
    "sambanova": ProviderDescriptor("sambanova", "SambaNova", "openai_compatible", "https://api.sambanova.ai/v1/chat/completions", "SAMBANOVA_API_KEY"),
    "perplexity": ProviderDescriptor("perplexity", "Perplexity", "openai_compatible", "https://api.perplexity.ai/chat/completions", "PERPLEXITY_API_KEY"),
    "moonshot": ProviderDescriptor("moonshot", "Moonshot / Kimi", "openai_compatible", "https://api.moonshot.ai/v1/chat/completions", "MOONSHOT_API_KEY"),
    "openrouter": ProviderDescriptor("openrouter", "OpenRouter", "openai_compatible", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "nvidia_nim": ProviderDescriptor("nvidia_nim", "NVIDIA NIM", "openai_compatible", "https://integrate.api.nvidia.com/v1/chat/completions", "NVIDIA_NIM_API_KEY"),
    "huggingface": ProviderDescriptor("huggingface", "Hugging Face Inference", "openai_compatible", "https://router.huggingface.co/v1/chat/completions", "HF_TOKEN"),
    "litellm": ProviderDescriptor("litellm", "LiteLLM Compatibility Layer", "litellm", None, None),
    "custom": ProviderDescriptor("custom", "Custom OpenAI-compatible", "openai_compatible", None, None),
}


def get(provider_id: str) -> ProviderDescriptor | None:
    return PROVIDERS.get(provider_id.strip().lower())


def all_providers() -> list[ProviderDescriptor]:
    return list(PROVIDERS.values())
