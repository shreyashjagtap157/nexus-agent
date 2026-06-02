"""
User Profile — Learns and stores user preferences.

Inspired by hermes agent's self-improving learning loop.
Stores coding style, preferred frameworks, common patterns.
"""

from __future__ import annotations

import copy
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class UserProfile:
    """Persistent user preference storage.

    Learns from interactions and stores preferences as structured YAML
    for transparency and editability.
    """

    DEFAULT_PROFILE = {
        "coding_style": {
            "language_preferences": [],
            "indentation": "auto",
            "line_length": "auto",
            "naming_convention": "auto",
            "documentation_style": "auto",
        },
        "preferences": {
            "frameworks": [],
            "tools": [],
            "testing_framework": "auto",
            "package_manager": "auto",
            "editor": "auto",
        },
        "behavior": {
            "verbosity": "normal",  # minimal, normal, detailed
            "auto_approve_safe": True,
            "preferred_mode": "auto",
            "show_thinking": True,
        },
        "learned_patterns": [],
        "last_updated": None,
    }

    def __init__(self, profile_path: str | Path):
        self.profile_path = Path(profile_path)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._profile: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load profile from YAML file."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, encoding="utf-8") as f:
                    self._profile = yaml.safe_load(f) or {}
            except (yaml.YAMLError, OSError) as e:
                logger.warning("Could not load user profile: %s", e)
                self._profile = {}

        # Deep-merge with defaults
        self._profile = self._deep_merge(self.DEFAULT_PROFILE, self._profile)

    @staticmethod
    def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge defaults with overrides, preferring overrides."""
        result = dict(defaults)
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = UserProfile._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _save(self) -> None:
        """Save profile to YAML file atomically."""
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix=".yaml",
                prefix="user_profile_",
                dir=self.profile_path.parent,
            )
            self._profile["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(self._profile, f, default_flow_style=False, sort_keys=False)
            fd = None
            os.replace(tmp_path, self.profile_path)
            tmp_path = None
        except (OSError, ValueError, TypeError) as e:
            logger.error("Could not save user profile: %s", e)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        """Get a profile value using dot notation (e.g., 'coding_style.indentation')."""
        with self._lock:
            keys = key.split(".")
            value = self._profile
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
                if value is None:
                    return default
            return value

    def set(self, key: str, value: Any) -> None:
        """Set a profile value using dot notation."""
        with self._lock:
            keys = key.split(".")
            target = self._profile
            for k in keys[:-1]:
                target = target.setdefault(k, {})
            target[keys[-1]] = value
            self._save()

    def learn_pattern(self, pattern: str, context: str = "") -> None:
        """Store a learned pattern from user interactions."""
        with self._lock:
            patterns = self._profile.get("learned_patterns", [])
            entry = {
                "pattern": pattern,
                "context": context,
                "learned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            patterns.append(entry)

            # Keep last 100 patterns
            if len(patterns) > 100:
                patterns = patterns[-100:]

            self._profile["learned_patterns"] = patterns
            self._save()

    def get_summary(self) -> str:
        """Get a text summary of user preferences for prompt injection."""
        with self._lock:
            parts: list[str] = []

            # Coding style
            style = self._profile.get("coding_style", {})
            if style.get("language_preferences"):
                parts.append(f"Preferred languages: {', '.join(style['language_preferences'])}")
            if style.get("indentation") != "auto":
                parts.append(f"Indentation: {style['indentation']}")

            # Preferences
            prefs = self._profile.get("preferences", {})
            if prefs.get("frameworks"):
                parts.append(f"Preferred frameworks: {', '.join(prefs['frameworks'])}")
            if prefs.get("testing_framework") != "auto":
                parts.append(f"Testing: {prefs['testing_framework']}")

            # Behavior
            behavior = self._profile.get("behavior", {})
            if behavior.get("verbosity") != "normal":
                parts.append(f"Verbosity: {behavior['verbosity']}")

            # Recent patterns
            patterns = self._profile.get("learned_patterns", [])
            if patterns:
                recent = patterns[-5:]
                parts.append("Recent patterns:")
                for p in recent:
                    parts.append(f"  - {p['pattern']}")

            return "\n".join(parts) if parts else ""

    def to_dict(self) -> dict[str, Any]:
        """Get full profile as dict."""
        with self._lock:
            return copy.deepcopy(self._profile)

    def close(self) -> None:
        """No-op. Profile is saved to disk on each mutation."""
