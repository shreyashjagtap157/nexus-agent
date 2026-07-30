"""Tests for input_handler_simple.py — MinimalInputHandlerMixin."""

import unittest
from unittest.mock import MagicMock, patch


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


from nexus_agent.cli.input_handler_simple import MinimalInputHandlerMixin


class TestReadInput(unittest.TestCase):
    """Test the simple input handler."""

    def setUp(self):
        self.app = _MockApp()
        self.app._handle_slash_command = MinimalInputHandlerMixin._handle_slash_command.__get__(
            self.app, type(self.app)
        )
        self.app._read_input = MinimalInputHandlerMixin._read_input.__get__(
            self.app, type(self.app)
        )

    @patch("builtins.input", return_value="hello")
    def test_read_input_returns_stripped(self, mock_input):
        result = self.app._read_input()
        self.assertEqual(result, "hello")

    @patch("builtins.input", return_value="")
    def test_read_input_empty_returns_none(self, mock_input):
        result = self.app._read_input()
        self.assertIsNone(result)

    @patch("builtins.input", return_value="   ")
    def test_read_input_whitespace_returns_none(self, mock_input):
        result = self.app._read_input()
        self.assertIsNone(result)

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_read_input_keyboard_interrupt(self, mock_input):
        result = self.app._read_input()
        self.assertIsNone(result)

    @patch("builtins.input", side_effect=EOFError)
    def test_read_input_eof(self, mock_input):
        result = self.app._read_input()
        self.assertIsNone(result)


class TestHandleSlashCommand(unittest.TestCase):
    """Test slash command handling."""

    def setUp(self):
        self.app = _MockApp()
        self.app._handle_slash_command = MinimalInputHandlerMixin._handle_slash_command.__get__(
            self.app, type(self.app)
        )
        self.app._minimal_help = MinimalInputHandlerMixin._minimal_help.__get__(
            self.app, type(self.app)
        )
        self.app.SLASH_COMMANDS = MinimalInputHandlerMixin.SLASH_COMMANDS
        self.app.console = MagicMock()

    def test_help_command(self):
        self.app._handle_slash_command("/help")
        self.app.r.divider.assert_called()

    @patch("sys.exit")
    def test_exit_command(self, mock_exit):
        with patch("builtins.print"):
            self.app._handle_slash_command("/exit")
            mock_exit.assert_called_with(0)

    @patch("sys.exit")
    def test_quit_command(self, mock_exit):
        with patch("builtins.print"):
            self.app._handle_slash_command("/quit")
            mock_exit.assert_called_with(0)

    def test_clear_command(self):
        self.app._handle_slash_command("/clear")
        self.app.r.console.clear.assert_called_once()
        self.app._rebuild_welcome.assert_called_once()

    def test_status_command(self):
        self.app._handle_slash_command("/status")
        self.app.r.system_message.assert_called_once()

    def test_unknown_command(self):
        self.app._handle_slash_command("/unknown")
        # BaseCommands delegation internally calls r.error for unknown commands
        self.assertTrue(self.app.r.error.called)

    def test_unknown_command_shows_error_message(self):
        self.app._handle_slash_command("/unknown")
        # At least one error call should mention "unknown"
        calls = [str(c) for c in self.app.r.error.call_args_list]
        self.assertTrue(any("unknown" in c.lower() for c in calls))

    def test_command_with_args(self):
        self.app.r.error = MagicMock()
        self.app._handle_slash_command("/help all")
        # /help takes no args in simple handler, but should not crash
        self.app.r.divider.assert_called()


class TestMinimalHelp(unittest.TestCase):
    """Test the minimal help display."""

    def setUp(self):
        self.app = _MockApp()
        self.app._minimal_help = MinimalInputHandlerMixin._minimal_help.__get__(
            self.app, type(self.app)
        )
        self.app.SLASH_COMMANDS = MinimalInputHandlerMixin.SLASH_COMMANDS
        self.app.console = MagicMock()

    def test_help_shows_divider(self):
        self.app._minimal_help()
        self.assertEqual(self.app.r.divider.call_count, 2)

    def test_help_prints_commands(self):
        self.app._minimal_help()
        self.assertTrue(self.app.console.print.called)

    def test_help_includes_common_commands(self):
        self.app._minimal_help()
        # Should have printed command names
        printed = [str(c) for c in self.app.console.print.call_args_list]
        all_text = " ".join(printed)
        self.assertIn("/help", all_text)


if __name__ == "__main__":
    unittest.main()
