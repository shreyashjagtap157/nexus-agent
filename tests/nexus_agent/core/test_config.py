"""Tests for the configuration system."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from nexus_agent.core.config import (
    load_config,
    save_config,
    save_user_config,
    _deep_merge,
    _apply_env_overrides,
    _strip_secrets,
)


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 3
        assert result["c"] == 4

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        result = _deep_merge(base, override)
        assert result["a"]["x"] == 1
        assert result["a"]["y"] == 3
        assert result["a"]["z"] == 4

    def test_deep_nested_merge(self):
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        result = _deep_merge(base, override)
        assert result["a"]["b"]["c"] == 1
        assert result["a"]["b"]["d"] == 2

    def test_no_mutation(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        _deep_merge(base, override)
        assert "y" not in base["a"]


class TestEnvOverrides:
    def test_gpu_layers_override(self):
        config = {"local_model": {}}
        with patch.dict(os.environ, {"NEXUS_GPU_LAYERS": "32"}):
            result = _apply_env_overrides(config)
            assert result["local_model"]["gpu_layers"] == 32

    def test_context_size_override(self):
        config = {"local_model": {}}
        with patch.dict(os.environ, {"NEXUS_CONTEXT_SIZE": "8192"}):
            result = _apply_env_overrides(config)
            assert result["local_model"]["context_size"] == 8192

    def test_effort_level_override(self):
        config = {"agent": {}}
        with patch.dict(os.environ, {"NEXUS_EFFORT_LEVEL": "high"}):
            result = _apply_env_overrides(config)
            assert result["agent"]["effort_level"] == "high"

    def test_invalid_int_skipped(self):
        config = {"local_model": {}}
        with patch.dict(os.environ, {"NEXUS_GPU_LAYERS": "not_a_number"}):
            result = _apply_env_overrides(config)
            assert "gpu_layers" not in result["local_model"]


class TestStripSecrets:
    def test_strips_api_key(self):
        config = {"providers": {"openai": {"api_key": "sk-123"}}}
        result = _strip_secrets(config)
        assert "api_key" not in result["providers"]["openai"]

    def test_preserves_non_secrets(self):
        config = {"agent": {"effort_level": "high"}}
        result = _strip_secrets(config)
        assert result["agent"]["effort_level"] == "high"

    def test_strips_nested_secrets(self):
        config = {"level1": {"secret_key": "abc123"}}
        result = _strip_secrets(config)
        assert "secret_key" not in result["level1"]


class TestLoadConfig:
    def test_default_config(self, tmp_path):
        config = load_config(workspace=tmp_path)
        assert "agent" in config
        assert "local_model" in config
        assert "permissions" in config

    def test_config_with_env(self, tmp_path):
        with patch.dict(os.environ, {"NEXUS_EFFORT_LEVEL": "max"}):
            config = load_config(workspace=tmp_path)
            assert config["agent"]["effort_level"] == "max"
