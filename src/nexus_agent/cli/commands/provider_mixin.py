"""Provider slash commands — /connect, /disconnect, and provider metadata."""

from __future__ import annotations

import os
import threading
import time

from nexus_agent.core.config import save_config


class ProviderCommandsMixin:
    """Mixin providing provider connection slash command handlers.

    Extracted from the monolithic command_dispatcher.py to reduce that
    file's size and group provider-related logic together.
    """

    _KNOWN_PROVIDERS = [
        ("Anthropic (Claude)", "anthropic"),
        ("OpenAI (GPT-4o, o-series)", "openai"),
        ("Google (Gemini)", "google"),
        ("Ollama (local Llama, Mistral, etc.)", "ollama"),
        ("OpenRouter (multi-model gateway)", "openrouter"),
        ("Groq (fast inference)", "groq"),
        ("DeepSeek", "deepseek"),
        ("AWS Bedrock (Claude, Llama on AWS)", "bedrock"),
        ("NVIDIA NIM (Nemotron, Llama-Nemotron)", "nvidia"),
        ("Mistral AI (Mistral, Codestral)", "mistral"),
        ("Fireworks AI (fast inference)", "fireworks"),
        ("Together AI (open-source models)", "together"),
        ("Perplexity (Sonar, Llama-3)", "perplexity"),
        ("Custom OpenAI-compatible", "custom"),
    ]

    _PROVIDER_META = {
        "openai":       {"base": "https://api.openai.com/v1",              "env_key": "OPENAI_API_KEY"},
        "anthropic":    {"base": "https://api.anthropic.com/v1",           "env_key": "ANTHROPIC_API_KEY"},
        "google":       {"base": "https://generativelanguage.googleapis.com/v1beta/openai", "env_key": "GEMINI_API_KEY"},
        "ollama":       {"base": "http://localhost:11434",                 "env_key": ""},
        "openrouter":   {"base": "https://openrouter.ai/api/v1",          "env_key": "OPENROUTER_API_KEY"},
        "groq":         {"base": "https://api.groq.com/openai/v1",        "env_key": "GROQ_API_KEY"},
        "deepseek":     {"base": "https://api.deepseek.com/v1",           "env_key": "DEEPSEEK_API_KEY"},
        "bedrock":      {"base": "",                                      "env_key": ""},
        "nvidia":       {"base": "https://integrate.api.nvidia.com/v1",   "env_key": "NVIDIA_API_KEY"},
        "mistral":      {"base": "https://api.mistral.ai/v1",             "env_key": "MISTRAL_API_KEY"},
        "fireworks":    {"base": "https://api.fireworks.ai/inference/v1", "env_key": "FIREWORKS_API_KEY"},
        "together":     {"base": "https://api.together.xyz/v1",           "env_key": "TOGETHER_API_KEY"},
        "perplexity":   {"base": "https://api.perplexity.ai",             "env_key": "PERPLEXITY_API_KEY"},
        "custom":       {"base": "",                                      "env_key": ""},
    }

    _HARDCODED_MODELS = {
        "anthropic": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-20250514",
            "claude-3-opus-20240229",
        ],
        "bedrock": [
            "anthropic.claude-sonnet-4-20250514-v2:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-5-haiku-20241022-v1:0",
            "anthropic.claude-opus-4-20250514-v1:0",
            "meta.llama3-70b-instruct-v1:0",
        ],
    }

    _PROVIDER_CONTEXT_SIZES = {
        "anthropic": 200000, "openai": 128000, "google": 1048576,
        "openrouter": 200000, "groq": 131072, "deepseek": 65536,
        "nvidia": 128000, "mistral": 128000, "fireworks": 131072,
        "together": 131072, "perplexity": 127000,
    }

    def _cmd_connect(self, args: str):
        """Interactive LLM provider connection flow."""
        self._interactive_connect_provider()

    def _cmd_disconnect(self, args: str):
        """Disconnect from current provider, return to local mode."""
        providers_cfg = self._config.setdefault("providers", {})
        providers_cfg["active"] = "local"
        self._provider_name = "local"
        save_config(self._config, self.config_path)
        self.r.system_message("Disconnected from provider, returning to local mode")
        # Re-init engine to switch back to local
        try:
            self._init_engine(skip_interactive=True)
            self._init_agent()
        except (RuntimeError, ValueError, OSError) as e:
            self.r.error(f"Failed to re-init local engine: {e}")
        self._rebuild_welcome()
