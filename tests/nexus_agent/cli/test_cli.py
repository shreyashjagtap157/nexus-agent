"""Tests for CLI module — renderer, auth, theme, models_db, runtime_manager key classes."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus_agent.cli.auth import AuthStore
from nexus_agent.cli.renderer import (
    ContextBreakdown,
    TokenUsage,
    Verbosity,
    detect_dark_mode,
)
from nexus_agent.cli.theme import DARK_THEME, LIGHT_THEME


class TestTheme(unittest.TestCase):
    def test_dark_theme_has_attributes(self):
        self.assertTrue(hasattr(DARK_THEME, "bg_primary"))
        self.assertTrue(hasattr(DARK_THEME, "text_primary"))
        self.assertTrue(hasattr(DARK_THEME, "accent_primary"))

    def test_light_theme_has_attributes(self):
        self.assertTrue(hasattr(LIGHT_THEME, "bg_primary"))
        self.assertTrue(hasattr(LIGHT_THEME, "text_primary"))


class TestVerbosity(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(Verbosity.QUIET.value, "quiet")
        self.assertEqual(Verbosity.NORMAL.value, "normal")
        self.assertEqual(Verbosity.VERBOSE.value, "verbose")


class TestTokenUsage(unittest.TestCase):
    def test_default_zeros(self):
        tu = TokenUsage()
        self.assertEqual(tu.input_tokens, 0)
        self.assertEqual(tu.output_tokens, 0)

    def test_total_tokens(self):
        tu = TokenUsage()
        tu.total_input = 100
        tu.total_output = 50
        self.assertEqual(tu.total, 150)

    def test_input_output_tokens(self):
        tu = TokenUsage()
        tu.input_tokens = 100
        tu.output_tokens = 50
        self.assertEqual(tu.input_tokens, 100)
        self.assertEqual(tu.output_tokens, 50)


class TestContextBreakdown(unittest.TestCase):
    def test_defaults(self):
        cb = ContextBreakdown()
        self.assertIsInstance(cb.system_prompt, int)
        self.assertGreater(cb.max_context, 0)
        self.assertGreaterEqual(cb.free_space, 0)


class TestDetectDarkMode(unittest.TestCase):
    @patch("os.environ.get")
    def test_dark_mode_default(self, mock_get):
        mock_get.return_value = ""
        self.assertTrue(detect_dark_mode())

    @patch("os.environ.get")
    def test_light_mode(self, mock_get):
        mock_get.return_value = "0;15"
        self.assertFalse(detect_dark_mode())

    @patch("os.environ.get")
    def test_invalid_env(self, mock_get):
        mock_get.return_value = "invalid"
        self.assertTrue(detect_dark_mode())


class TestAuthStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.auth_dir = Path(self.tmpdir.name) / ".nexus-agent"
        self.auth_dir.mkdir(parents=True)
        self.store = AuthStore(data_dir=str(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_and_get_key(self):
        self.store.save_key("openai", "sk-test123")
        key = self.store.get_key("openai")
        self.assertEqual(key, "sk-test123")

    def test_get_nonexistent(self):
        key = self.store.get_key("nonexistent")
        self.assertIsNone(key)

    def test_has_key(self):
        self.store.save_key("openai", "sk-test")
        self.assertTrue(self.store.has_key("openai"))
        self.assertFalse(self.store.has_key("nope"))

    def test_remove_key(self):
        self.store.save_key("anthropic", "sk-ant-test")
        self.assertTrue(self.store.remove_key("anthropic"))
        self.assertIsNone(self.store.get_key("anthropic"))

    def test_list_providers(self):
        self.store.save_key("p1", "key1")
        self.store.save_key("p2", "key2")
        providers = self.store.list_providers()
        self.assertIn("p1", providers)

    def test_get_env_key(self):
        key = self.store.get_env_key("openai")
        self.assertIsInstance(key, str)

    def test_persistence(self):
        self.store.save_key("openai", "sk-persist")
        store2 = AuthStore(data_dir=str(self.tmpdir.name))
        self.assertEqual(store2.get_key("openai"), "sk-persist")
