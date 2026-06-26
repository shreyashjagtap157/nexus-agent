"""Tests for input_handler_simple.py — MinimalInputHandlerMixin."""

import sys
from unittest.mock import MagicMock

sys.modules["blessed"] = MagicMock()

import unittest  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402


class _MockApp:
    """Minimal app that satisfies MinimalInputHandlerMixin attribute requirements."""

    def __init__(self):
        self.r = MagicMock()
        self.r.divider = MagicMock()
        self.r.error = MagicMock()
        self.r.system_message = MagicMock()
        self.r.console = MagicMock()
        self._config = {"agent": {"effort_level": "medium"}}
        self._current_mode = MagicMock()
        self._current_mode.value = "auto"
        self._rebuild_welcome = MagicMock()


from nexus_agent.cli.input_handler_simple import MinimalInputHandlerMixin  # noqa: E402


class TestReadInput(unittest.TestCase):
    """Test the simple input handler."""

    def setUp(self):
        self.app = _MockApp()
        self.mixin = MinimalInputHandlerMixin()
        self.mixin.app = self.app
        self.mixin.r = self.app.r
        self.mixin.console = self.app.r.console
        self.mixin._config = self.app._config
        self.mixin._current_mode = self.app._current_mode
        self.mixin._rebuild_welcome = self.app._rebuild_welcome

    @patch("builtins.input")
    def test_read_input_normal_text(self, mock_input):
        """Test typing normal text."""
        mock_input.return_value = "Hello AI"

        result = self.mixin._read_input()
        self.assertEqual(result, "Hello AI")

    @patch("builtins.input")
    def test_read_input_keyboard_interrupt(self, mock_input):
        """Test Ctrl+C returns None."""
        mock_input.side_effect = KeyboardInterrupt

        result = self.mixin._read_input()
        self.assertIsNone(result)

    @patch("builtins.input")
    def test_read_input_eof(self, mock_input):
        """Test Ctrl+D returns None."""
        mock_input.side_effect = EOFError

        result = self.mixin._read_input()
        self.assertIsNone(result)

    @patch("sys.exit")
    def test_handle_slash_command_exit(self, mock_exit):
        """Test /exit slash command."""
        self.mixin._handle_slash_command("/exit")
        mock_exit.assert_called_with(0)

    def test_handle_slash_command_clear(self):
        """Test /clear slash command."""
        self.mixin._handle_slash_command("/clear")
        self.app.r.console.clear.assert_called_once()
        self.app._rebuild_welcome.assert_called_once()

    def test_handle_slash_command_status(self):
        """Test /status slash command."""
        self.mixin._handle_slash_command("/status")
        self.app.r.system_message.assert_called_once()

    def test_minimal_help(self):
        """Test minimal help command."""
        self.mixin._minimal_help()
        self.app.r.divider.assert_called()
        self.app.r.console.print.assert_called()
