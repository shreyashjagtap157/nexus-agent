"""
Configuration loader for NexusAgent.

Loads configuration from:
1. Default config (config/default.yaml)
2. User config (~/.nexus-agent/config.yaml)
3. Project config (.nexus-agent.yaml in workspace)
4. Environment variables (NEXUS_*)
5. CLI arguments (highest priority)
"""

import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

import yaml

logger = logging.getLogger(__name__)

import platformdirs

APP_NAME = "nexus-agent"
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "_default_config.yaml"


def get_data_dir(override: str | None = None) -> Path:
    """Get the data directory for NexusAgent."""
    if override:
        return Path(override).expanduser().resolve()

    env_dir = os.environ.get("NEXUS_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    return Path(platformdirs.user_data_dir(APP_NAME)).resolve()


def get_config_dir() -> Path:
    """Get the config directory."""
    return Path(platformdirs.user_config_dir(APP_NAME)).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file with UTF-8 encoding."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict, _depth: int = 0) -> dict:
    """Deep merge two dicts, with override taking precedence.

    Includes a recursion-depth guard to prevent infinite recursion.
    """
    MAX_DEPTH = 20
    if _depth > MAX_DEPTH:
        logger.warning("Maximum recursion depth exceeded in _deep_merge, using override value")
        return deepcopy(override)
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value, _depth + 1)
        else:
            result[key] = deepcopy(value)
    return result


def _apply_env_overrides(config: dict) -> dict:
    """Apply environment variable overrides to config."""
    env_mappings = {
        "NEXUS_MODELS_DIR": ("local_model", "models_dir"),
        "NEXUS_DEFAULT_MODEL": ("local_model", "default_model"),
        "NEXUS_GPU_LAYERS": ("local_model", "gpu_layers"),
        "NEXUS_CONTEXT_SIZE": ("local_model", "context_size"),
        "NEXUS_THREADS": ("local_model", "threads"),
        "NEXUS_RUNTIME": ("local_model", "runtime"),
        "NEXUS_EFFORT_LEVEL": ("agent", "effort_level"),
        "NEXUS_PERMISSION_MODE": ("permissions", "mode"),
        "NEXUS_GUI_HOST": ("gui", "host"),
        "NEXUS_GUI_PORT": ("gui", "port"),
        "NEXUS_DEFAULT_PROVIDER": ("model", "provider"),
        "NEXUS_DEFAULT_MODEL_ID": ("model", "id"),
    }

    int_keys = {"NEXUS_GPU_LAYERS", "NEXUS_CONTEXT_SIZE", "NEXUS_THREADS", "NEXUS_GUI_PORT"}

    for env_key, config_path in env_mappings.items():
        value = os.environ.get(env_key)
        if value is not None and value != "":
            # Navigate to the right nesting level
            target = config
            for key in config_path[:-1]:
                target = target.setdefault(key, {})

            if env_key in int_keys:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid integer value for {env_key}: {value!r}")
                    continue
            target[config_path[-1]] = value

    return config


class LocalModelConfig(TypedDict, total=False):
    models_dir: str
    default_model: str
    gpu_layers: int
    context_size: int
    threads: int
    runtime: str


class PermissionsConfig(TypedDict, total=False):
    mode: str


class GuiConfig(TypedDict, total=False):
    host: str
    port: int


class ModelConfig(TypedDict, total=False):
    provider: str
    id: str


class AgentConfig(TypedDict, total=False):
    effort_level: str
    default_mode: str
    max_iterations: int
    max_tokens: int
    temperature: float
    streaming: bool


class NexusAgentConfig(TypedDict, total=False):
    local_model: LocalModelConfig
    agent: AgentConfig
    permissions: PermissionsConfig
    gui: GuiConfig
    model: ModelConfig
    _data_dir: str


def load_config(
    config_path: str | None = None,
    workspace: Path | None = None,
    data_dir: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> NexusAgentConfig:
    """Load and merge configuration from all sources.

    Priority (lowest to highest):
    1. Default config
    2. User config
    3. Project config
    4. Environment variables
    5. Explicit config file (--config)
    6. CLI arguments
    """
    # 1. Default config
    config: dict[str, Any] = {}
    if DEFAULT_CONFIG_PATH.exists():
        config = _load_yaml(DEFAULT_CONFIG_PATH)

    # 2. User config
    user_config_path = get_config_dir() / "config.yaml"
    if user_config_path.exists():
        user_config = _load_yaml(user_config_path)
        config = _deep_merge(config, user_config)

    # 3. Project config
    if workspace:
        project_config_path = workspace / ".nexus-agent.yaml"
        if project_config_path.exists():
            project_config = _load_yaml(project_config_path)
            config = _deep_merge(config, project_config)

    # 4. Environment variables
    config = _apply_env_overrides(config)

    # 5. Explicit config file
    if config_path:
        explicit_path = Path(config_path)
        if explicit_path.exists():
            explicit_config = _load_yaml(explicit_path)
            config = _deep_merge(config, explicit_config)

    # 6. CLI overrides
    if cli_overrides:
        config = _deep_merge(config, cli_overrides)

    # Set data directory
    config["_data_dir"] = str(get_data_dir(data_dir))

    return config


def _strip_secrets(cfg: dict) -> dict:
    """Return a copy of cfg with internal keys and API keys removed."""
    SECRET_KEYS = {"api_key", "api_secret", "secret_key", "password", "token",
                   "access_token", "refresh_token", "private_key", "client_secret"}
    out = {}
    for k, v in cfg.items():
        if k.startswith("_"):
            continue
        if k.lower() in SECRET_KEYS:
            continue
        if isinstance(v, dict):
            out[k] = _strip_secrets(v)
        else:
            out[k] = deepcopy(v)
    return out


def save_config(config: dict[str, Any], config_path: str | None = None) -> None:
    """Save config to file (internal keys and API keys are stripped)."""
    if config_path:
        p = Path(config_path)
    else:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        p = config_dir / "config.yaml"
    clean = _strip_secrets(config)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(clean, f, default_flow_style=False, sort_keys=False)


def save_user_config(updates: dict[str, Any]) -> None:
    """Save updates to user config file (secrets stripped)."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"

    existing: dict[str, Any] = {}
    if config_path.exists():
        existing = _load_yaml(config_path)

    merged = _deep_merge(existing, updates)
    clean = _strip_secrets(merged)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(clean, f, default_flow_style=False, sort_keys=False)
