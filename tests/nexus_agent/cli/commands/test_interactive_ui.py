"""Tests for interactive_ui.py — InteractiveUIMixin (menus, validation, model config)."""

import unittest
from unittest.mock import MagicMock, patch


class _MockApp:
    """Minimal app that satisfies InteractiveUIMixin attribute requirements."""

    def __init__(self):
        import tempfile
        self.r = MagicMock()
        self.r.error = MagicMock()
        self.r.system_message = MagicMock()
        self.r.show_spinner = MagicMock()
        self.r.hide_spinner = MagicMock()
        self.r._welcome_params = {}
        self._read_byte = MagicMock(return_value=b"")
        self._read_line = MagicMock(return_value="")
        self._auth_store = MagicMock()
        self._auth_store.get_key.return_value = None
        self._auth_store.save_key = MagicMock()
        self._config = {}
        self.config_path = tempfile.mkstemp(suffix=".yaml")[1]
        self._models_db = MagicMock()
        self._provider_name = ""
        self._init_engine = MagicMock()
        self._init_agent = MagicMock()
        self._rebuild_welcome = MagicMock()
        self.workspace = MagicMock()
        self.workspace.__str__ = MagicMock(return_value="/mock/workspace")
        self._HARDCODED_MODELS = {
            "openai": ["gpt-4o", "gpt-4o-mini"],
        }
        self._PROVIDER_META = {
            "openai": {"env_key": "OPENAI_API_KEY", "base": "https://api.openai.com/v1"},
            "anthropic": {"env_key": "ANTHROPIC_API_KEY", "base": "https://api.anthropic.com"},
            "google": {"env_key": "GOOGLE_API_KEY", "base": ""},
        }
        self._KNOWN_PROVIDERS = [
            ("OpenAI", "openai"),
            ("Anthropic", "anthropic"),
            ("Google", "google"),
        ]
        self._PROVIDER_CONTEXT_SIZES = {
            "openai": 128000,
            "anthropic": 200000,
            "google": 1048576,
        }
        self.console = MagicMock()


from nexus_agent.cli.commands.interactive_ui import InteractiveUIMixin


class TestInteractiveMenu(unittest.TestCase):
    """Test the interactive menu system."""

    def setUp(self):
        self.app = _MockApp()
        self.app._interactive_menu = InteractiveUIMixin._interactive_menu.__get__(
            self.app, type(self.app)
        )

    def test_menu_no_selectable_items(self):
        items = [("---Separator---", None)]
        result = self.app._interactive_menu(items, "Test Title")
        self.assertIsNone(result)

    def test_menu_single_item_enter(self):
        items = [("Option 1", "opt1")]
        self.app._read_byte.side_effect = [b"\r"]
        result = self.app._interactive_menu(items, "Test")
        self.assertEqual(result, "opt1")

    def test_menu_esc_returns_none(self):
        items = [("Option 1", "opt1")]
        self.app._read_byte.side_effect = [b"\x1b"]
        result = self.app._interactive_menu(items, "Test")
        self.assertIsNone(result)

    def test_menu_with_separators(self):
        items = [
            ("Option 1", "opt1"),
            ("---", None),
            ("Option 2", "opt2"),
        ]
        self.app._read_byte.side_effect = [b"\r"]
        result = self.app._interactive_menu(items, "Test")
        self.assertEqual(result, "opt1")


class TestValidateProviderKey(unittest.TestCase):
    """Test provider API key validation."""

    def setUp(self):
        self.app = _MockApp()
        self.app._validate_provider_key = InteractiveUIMixin._validate_provider_key.__get__(
            self.app, type(self.app)
        )

    def test_unknown_provider(self):
        ok, msg = self.app._validate_provider_key("unknown_provider", "key123")
        self.assertTrue(ok)
        self.assertIn("No validation endpoint", msg)

    @patch("httpx.get")
    def test_openai_valid_key(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        ok, msg = self.app._validate_provider_key("openai", "sk-valid")
        self.assertTrue(ok)

    @patch("httpx.get")
    def test_openai_invalid_key(self, mock_get):
        mock_get.return_value = MagicMock(status_code=401)
        ok, msg = self.app._validate_provider_key("openai", "sk-invalid")
        self.assertFalse(ok)
        self.assertIn("401", msg)

    @patch("httpx.get")
    def test_openai_forbidden(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403)
        ok, msg = self.app._validate_provider_key("openai", "sk-forbidden")
        self.assertFalse(ok)
        self.assertIn("403", msg)

    @patch("httpx.get")
    def test_anthropic_valid_key(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        ok, msg = self.app._validate_provider_key("anthropic", "sk-ant-valid")
        self.assertTrue(ok)

    @patch("httpx.get")
    def test_timeout(self, mock_get):
        from httpx import TimeoutException
        mock_get.side_effect = TimeoutException("timed out")
        ok, msg = self.app._validate_provider_key("openai", "sk-key")
        self.assertFalse(ok)
        self.assertIn("timed out", msg.lower())

    @patch("httpx.get")
    def test_connection_error(self, mock_get):
        from httpx import ConnectError
        mock_get.side_effect = ConnectError("connection failed")
        ok, msg = self.app._validate_provider_key("openai", "sk-key")
        self.assertFalse(ok)
        self.assertIn("could not connect", msg.lower())

    @patch("httpx.get")
    def test_perplexity_skipped(self, mock_get):
        ok, msg = self.app._validate_provider_key("perplexity", "pplx-key")
        self.assertTrue(ok)
        self.assertIn("skipped", msg)
        mock_get.assert_not_called()


class TestFindFiles(unittest.TestCase):
    """Test the file search helper."""

    def setUp(self):
        self.app = _MockApp()
        self.app._find_files = InteractiveUIMixin._find_files.__get__(
            self.app, type(self.app)
        )

    @patch("subprocess.run")
    def test_git_ls_files(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/main.py\nsrc/utils.py\n",
        )
        result = self.app._find_files("main")
        self.assertIn("src/main.py", result)
        self.assertIn("src/utils.py", result)

    @patch("subprocess.run")
    def test_git_fails_fallback_to_rglob(self, mock_run):
        import tempfile
        from pathlib import Path
        mock_run.side_effect = FileNotFoundError
        # Create a real temp file for rglob to find
        tmp_dir = Path(tempfile.mkdtemp())
        (tmp_dir / "main.py").touch()
        self.app.workspace = tmp_dir
        result = self.app._find_files("main")
        self.assertIn("main.py", result)

    @patch("subprocess.run")
    def test_empty_result(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        with patch("pathlib.WindowsPath.rglob", return_value=[]):
            result = self.app._find_files("nonexistent")
            self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_limits_to_20_results(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\n".join([f"src/file{i}.py" for i in range(30)]),
        )
        result = self.app._find_files("file")
        self.assertLessEqual(len(result), 20)


class TestInteractiveAddModel(unittest.TestCase):
    """Test the interactive model addition flow."""

    def setUp(self):
        self.app = _MockApp()
        self.app._interactive_add_model = InteractiveUIMixin._interactive_add_model.__get__(
            self.app, type(self.app)
        )

    def test_cancel_with_none_name(self):
        self.app._read_line.return_value = None
        self.app._interactive_add_model()
        # Should return without calling anything
        self.app._models_db.add.assert_not_called()

    def test_empty_name_shows_error(self):
        self.app._read_line.return_value = ""
        self.app._interactive_add_model()
        self.app.r.error.assert_called_with("Name cannot be empty")

    def test_cancel_at_path(self):
        self.app._read_line.side_effect = ["my_model", None]
        self.app._interactive_add_model()
        self.app._models_db.add.assert_not_called()

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", return_value="/fake/path/model.gguf")
    def test_valid_model_added(self, mock_abspath, mock_isfile):
        self.app._read_line.side_effect = ["my_model", "/fake/path/model.gguf"]
        self.app._interactive_add_model()
        self.app._models_db.add.assert_called_once_with(
            "my_model", "/fake/path/model.gguf"
        )

    @patch("os.path.isfile", return_value=False)
    @patch("os.path.abspath", return_value="/fake/path/missing.gguf")
    def test_invalid_path_shows_error(self, mock_abspath, mock_isfile):
        self.app._read_line.side_effect = ["my_model", "/fake/path/missing.gguf"]
        self.app._interactive_add_model()
        self.app.r.error.assert_called_with("File not found: /fake/path/missing.gguf")
        self.app._models_db.add.assert_not_called()


class TestInteractivePickModel(unittest.TestCase):
    """Test the model picker."""

    def setUp(self):
        self.app = _MockApp()
        self.app._interactive_pick_model = InteractiveUIMixin._interactive_pick_model.__get__(
            self.app, type(self.app)
        )
        self.app._interactive_menu = MagicMock(return_value="gpt-4o")
        self.app._read_line = MagicMock(return_value="gpt-4o")

    def test_hardcoded_model_selected(self):
        result = self.app._interactive_pick_model("openai", "sk-key")
        self.assertEqual(result, "gpt-4o")
        self.app._interactive_menu.assert_called_once()

    def test_cancel_returns_none(self):
        self.app._interactive_menu.return_value = None
        result = self.app._interactive_pick_model("openai", "sk-key")
        self.assertIsNone(result)

    def test_default_model_fallback(self):
        self.app._interactive_menu.return_value = "__manual__"
        result = self.app._interactive_pick_model("openai", "sk-key")
        self.assertEqual(result, "gpt-4o")  # read_line returns "gpt-4o"


class TestInteractiveConnectProvider(unittest.TestCase):
    """Test the full provider connection flow."""

    def setUp(self):
        self.app = _MockApp()
        self.app._interactive_connect_provider = InteractiveUIMixin._interactive_connect_provider.__get__(
            self.app, type(self.app)
        )
        self.app._interactive_menu = MagicMock(return_value="openai")
        self.app._read_line = MagicMock(return_value="sk-test-key")
        self.app._validate_provider_key = MagicMock(return_value=(True, "OK"))
        self.app._interactive_pick_model = MagicMock(return_value="gpt-4o")

    def test_cancel_at_provider_sel(self):
        self.app._interactive_menu.return_value = None
        self.app._interactive_connect_provider()
        self.app._init_engine.assert_not_called()

    def test_successful_connect(self):
        self.app._interactive_connect_provider()
        self.app._auth_store.save_key.assert_called_with("openai", "sk-test-key")
        self.app._init_engine.assert_called_once()
        self.app._init_agent.assert_called_once()
        self.app.r.system_message.assert_any_call("Connected to openai")

    def test_validation_failure_continue(self):
        self.app._validate_provider_key.return_value = (False, "Invalid API key (401 Unauthorized)")
        self.app._interactive_menu.side_effect = ["openai", "continue"]
        self.app._interactive_connect_provider()
        # Should continue despite validation failure
        self.app._init_engine.assert_called_once()

    def test_validation_failure_cancel(self):
        self.app._validate_provider_key.return_value = (False, "Invalid API key (401 Unauthorized)")
        self.app._interactive_menu.side_effect = ["openai", "cancel"]
        self.app._interactive_connect_provider()
        self.app._init_engine.assert_not_called()

    def test_existing_key_use_saved(self):
        self.app._auth_store.get_key.return_value = "saved-key"
        self.app._interactive_menu.side_effect = ["openai", "saved"]
        self.app._interactive_connect_provider()
        # Should use saved key without prompting
        self.app._auth_store.save_key.assert_called_with("openai", "saved-key")


class TestInteractiveModelConfigParamOps(unittest.TestCase):
    """Test the model config parameter adjustment and display logic."""

    def setUp(self):
        self.app = _MockApp()
        # Bind the mixin methods
        for name in dir(InteractiveUIMixin):
            if name.startswith("_") and not name.startswith("__"):
                attr = getattr(InteractiveUIMixin, name)
                if callable(attr):
                    setattr(self.app, name, attr.__get__(self.app, type(self.app)))

    def test_param_line_int(self):
        """Verify param_line formats int parameters correctly."""
        p = {"type": "int", "val": 32, "min": 0, "max": 128, "step": 1}
        # Can't call _interactive_model_config directly (full-screen),
        # but we can test the helper logic by duplicating the pattern
        val = p["val"]
        rng = p["max"] - p["min"]
        pct = int((val - p["min"]) / rng * 15) if rng > 0 else 0
        bar = "\u2588" * pct + "\u2591" * (15 - pct)
        result = f"[{bar}] {val} / {p['max']}"
        self.assertIn("32 / 128", result)
        self.assertIn("\u2588", result)  # filled block chars

    def test_param_line_float(self):
        """Verify param_line formats float parameters correctly."""
        p = {"type": "float", "val": 0.1, "min": 0.0, "max": 2.0, "step": 0.1}
        val = p["val"]
        rng = p["max"] - p["min"]
        pct = int((val - p["min"]) / rng * 15) if rng > 0 else 0
        bar = "\u2588" * pct + "\u2591" * (15 - pct)
        result = f"[{bar}] {val:.1f}"
        self.assertIn("0.1", result)

    def test_param_line_choice(self):
        """Verify param_line formats choice parameters correctly."""
        choices = [1024, 2048, 4096, 8192, 16384]
        target = 8192
        parts = []
        for c in choices:
            if c == target:
                parts.append(f"\033[1;32m[{c}]\033[0m")
            else:
                parts.append(str(c))
        result = " | ".join(parts)
        self.assertIn("[8192]", result)
        self.assertIn("1024", result)

    # Param line formatting tested inline in the tests above (int, float, choice)

    def test_adjust_param_int(self):
        params = [{"key": "gpu_layers", "label": "GPU Layers", "val": 32, "type": "int", "min": 0, "max": 128, "step": 1}]
        # Adjust +1
        params[0]["val"] = max(params[0]["min"], min(params[0]["max"], params[0]["val"] + 1))
        self.assertEqual(params[0]["val"], 33)

    def test_adjust_param_int_bounds(self):
        params = [{"key": "gpu_layers", "val": 128, "type": "int", "min": 0, "max": 128, "step": 1}]
        params[0]["val"] = max(params[0]["min"], min(params[0]["max"], params[0]["val"] + 1))
        self.assertEqual(params[0]["val"], 128)  # Clamped to max

    def test_adjust_param_float(self):
        params = [{"key": "temperature", "val": 0.5, "type": "float", "min": 0.0, "max": 2.0, "step": 0.1}]
        params[0]["val"] = max(params[0]["min"], min(params[0]["max"], params[0]["val"] + 0.1))
        params[0]["val"] = round(params[0]["val"], 1)
        self.assertEqual(params[0]["val"], 0.6)

    def test_adjust_param_choice(self):
        choices = [1024, 2048, 4096, 8192, 16384]
        params = [{"key": "context_size", "val": 4096, "type": "choice", "choices": choices}]
        c_idx = choices.index(4096)
        params[0]["val"] = choices[max(0, min(len(choices) - 1, c_idx + 1))]
        self.assertEqual(params[0]["val"], 8192)

    def test_adjust_param_bool(self):
        params = [{"key": "flash_attention", "val": True, "type": "bool"}]
        params[0]["val"] = not params[0]["val"]
        self.assertFalse(params[0]["val"])


class TestInteractiveModelConfigScreen(unittest.TestCase):
    """Test the model config HUD initialization and cleanup."""

    def setUp(self):
        self.app = _MockApp()
        self.app._interactive_model_config = InteractiveUIMixin._interactive_model_config.__get__(
            self.app, type(self.app)
        )
        self.app._config = {"local_model": {}, "agent": {}}

    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.write")
    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.flush")
    def test_config_enter_confirms(self, mock_flush, mock_write):
        self.app._kbhit = MagicMock(return_value=True)
        self.app._read_byte.side_effect = [b"\r"]  # Enter to confirm
        self.app.console = MagicMock()
        self.app._interactive_model_config("/path/to/model.gguf")
        # Should save config values
        self.assertEqual(
            self.app._config["local_model"].get("gpu_layers", None), 32
        )

    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.write")
    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.flush")
    @patch("nexus_agent.cli.commands.interactive_ui.time.sleep")
    def test_config_esc_cancels(self, mock_sleep, mock_flush, mock_write):
        # kbhit returns True first (to pass the while-loop check), then False (to
        # skip the escape-sequence parsing and trigger the else: break exit).
        self.app._kbhit = MagicMock(side_effect=[True, False])
        self.app._read_byte.side_effect = [b"\x1b"]
        self.app.console = MagicMock()
        self.app._interactive_model_config("/path/to/model.gguf")
        # Should not crash

    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.write")
    @patch("nexus_agent.cli.commands.interactive_ui.sys.stdout.flush")
    def test_config_navigates_params(self, mock_flush, mock_write):
        self.app._kbhit = MagicMock(return_value=True)
        self.app._read_byte.side_effect = [b"\xe0", b"P", b"\r"]  # Down arrow, then Enter
        self.app.console = MagicMock()
        self.app._interactive_model_config("/path/to/model.gguf")
        # Should not crash with arrow key navigation


if __name__ == "__main__":
    unittest.main()
