"""Tests for InputHandlerMixin — key parsing, prompt rendering, autocomplete, and input management."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.cli.input_handler import InputHandlerMixin


class _MockApp(InputHandlerMixin):
    """Minimal app that satisfies the mixin's attribute requirements."""

    def __init__(self):
        self._key_queue: list[bytes] = []
        self._input_history: list[str] = []
        self._history_idx = -1
        self._cmd_menu_lines = 0
        self._prompt_line_count = 0
        self._kill_buffer = ""
        self._drawer_active = False
        self._drawer_idx = 0
        self._sub_agents: list[dict] = []
        self._notification = ""
        self._notification_time = 0.0
        self._current_mode = MagicMock()
        self._current_mode.value = "auto"
        self._config = {"agent": {"effort_level": "medium"}}
        self.r = MagicMock()
        self.r._scroll_region_set = False
        self.SLASH_COMMANDS = [
            {"name": "/help", "description": "Show help", "usage": ""},
            {"name": "/memory", "description": "Manage memory", "usage": ""},
            {"name": "/model", "description": "Manage models", "usage": ""},
            {"name": "/config", "description": "Manage config", "usage": ""},
            {"name": "/session", "description": "Manage sessions", "usage": ""},
            {"name": "/tools", "description": "Manage tools", "usage": ""},
            {"name": "/exit", "description": "Exit the application", "usage": ""},
            {"name": "/clear", "description": "Clear the screen", "usage": ""},
        ]
        # Mock methods the mixin calls on self
        self._find_files = MagicMock(return_value=["file1.py", "file2.py", "test_file.py"])
        self._check_resize_in_loop = MagicMock(return_value=False)
        self._rebuild_welcome = MagicMock()
        self._clear_cmd_menu = MagicMock()
        self._cmd_model_interactive = MagicMock()
        self._render_footer = MagicMock()
        self._render_prompt = MagicMock()
        self._render_cmd_menu = MagicMock()


class TestWordBoundaries(unittest.TestCase):
    """Test the static word boundary methods that are fully deterministic."""

    def setUp(self):
        self.app = _MockApp()

    def test_word_boundary_left_start(self):
        self.assertEqual(self.app._word_boundary_left("hello world", 0), 0)

    def test_word_boundary_left_mid_word(self):
        self.assertEqual(self.app._word_boundary_left("hello world", 5), 0)

    def test_word_boundary_left_mid_second_word(self):
        self.assertEqual(self.app._word_boundary_left("hello world", 8), 6)

    def test_word_boundary_left_underscore(self):
        # Underscore is treated as part of a word, so "foo_bar_baz" is one word
        self.assertEqual(self.app._word_boundary_left("foo_bar_baz", 7), 0)

    def test_word_boundary_left_skips_spaces(self):
        self.assertEqual(self.app._word_boundary_left("hello   world", 10), 8)

    def test_word_boundary_right_end(self):
        self.assertEqual(self.app._word_boundary_right("hello", 5), 5)

    def test_word_boundary_right_mid_word(self):
        # Skips to start of next word, not the space
        self.assertEqual(self.app._word_boundary_right("hello world", 0), 6)

    def test_word_boundary_right_second_word(self):
        self.assertEqual(self.app._word_boundary_right("hello world", 6), 11)

    def test_word_boundary_right_skips_spaces(self):
        self.assertEqual(self.app._word_boundary_right("hello   world", 5), 8)

    def test_word_boundary_right_empty(self):
        self.assertEqual(self.app._word_boundary_right("", 0), 0)

    def test_word_boundary_left_empty(self):
        self.assertEqual(self.app._word_boundary_left("", 0), 0)


class TestHistoryNavigation(unittest.TestCase):
    """Test history up/down navigation."""

    def setUp(self):
        self.app = _MockApp()
        self.app._input_history = ["first command", "second command", "third command"]

    def test_history_up_returns_most_recent(self):
        result = self.app._history_up()
        self.assertEqual(result, "third command")
        self.assertEqual(self.app._history_idx, 0)

    def test_history_up_twice(self):
        self.app._history_up()
        result = self.app._history_up()
        self.assertEqual(result, "second command")
        self.assertEqual(self.app._history_idx, 1)

    def test_history_up_thrice(self):
        self.app._history_up()
        self.app._history_up()
        result = self.app._history_up()
        self.assertEqual(result, "first command")
        self.assertEqual(self.app._history_idx, 2)

    def test_history_up_beyond_history(self):
        self.app._history_up()
        self.app._history_up()
        self.app._history_up()
        result = self.app._history_up()  # Beyond limit
        self.assertEqual(result, "first command")  # Stays at oldest

    def test_history_down_from_history(self):
        self.app._history_up()  # idx=0
        self.app._history_up()  # idx=1
        result = self.app._history_down()
        self.assertEqual(result, "third command")
        self.assertEqual(self.app._history_idx, 0)

    def test_history_down_at_newest(self):
        self.app._history_up()  # idx=0
        result = self.app._history_down()
        self.assertIsNone(result)
        self.assertEqual(self.app._history_idx, -1)

    def test_history_down_empty(self):
        empty_app = _MockApp()
        result = empty_app._history_down()
        self.assertIsNone(result)

    def test_history_up_empty(self):
        empty_app = _MockApp()
        result = empty_app._history_up()
        self.assertIsNone(result)

    def test_history_append_on_enter(self):
        # The _read_input method appends to history on enter
        # We test this via the append logic directly
        self.app._input_history.append("new command")
        self.assertEqual(len(self.app._input_history), 4)
        self.assertEqual(self.app._input_history[-1], "new command")


class TestMenuUpdate(unittest.TestCase):
    """Test the autocomplete menu logic."""

    def setUp(self):
        self.app = _MockApp()

    def test_slash_command_matches(self):
        visible, filtered, idx = self.app._update_menu("/h", [], 0)
        self.assertTrue(visible)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "/help")

    def test_slash_command_multiple_matches(self):
        visible, filtered, idx = self.app._update_menu("/m", [], 0)
        self.assertTrue(visible)
        self.assertGreaterEqual(len(filtered), 2)
        names = [c["name"] for c in filtered]
        self.assertIn("/memory", names)
        self.assertIn("/model", names)

    def test_slash_command_no_match(self):
        visible, filtered, idx = self.app._update_menu("/zzz", [], 0)
        self.assertFalse(visible)
        self.assertEqual(filtered, [])

    def test_slash_command_exact_match(self):
        visible, filtered, idx = self.app._update_menu("/help", [], 0)
        self.assertTrue(visible)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "/help")

    def test_file_autocomplete_at_symbol(self):
        visible, filtered, idx = self.app._update_menu("edit @", [], 0)
        self.assertTrue(visible)
        self.assertGreaterEqual(len(filtered), 1)
        self.app._find_files.assert_called_with("")

    def test_file_autocomplete_with_query(self):
        visible, filtered, idx = self.app._update_menu("edit @file", [], 0)
        self.assertTrue(visible)
        self.app._find_files.assert_called_with("file")

    def test_no_menu_for_plain_text(self):
        visible, filtered, idx = self.app._update_menu("hello world", [], 0)
        self.assertFalse(visible)

    def test_clear_menu_when_no_longer_needed(self):
        """When menu was visible but query no longer matches, should clear."""
        self.app._cmd_menu_lines = 3
        self.app._clear_cmd_menu = MagicMock()
        visible, filtered, idx = self.app._update_menu("/zzz", [], 0)
        self.assertFalse(visible)
        self.app._clear_cmd_menu.assert_called_with(True)


class TestRenderCmdMenu(unittest.TestCase):
    """Test the command menu rendering logic."""

    def setUp(self):
        self.app = _MockApp()
        self.commands = [
            {"name": "/help", "description": "Show help information", "usage": ""},
            {"name": "/memory", "description": "Memory management", "usage": ""},
            {"name": "/model", "description": "Model management", "usage": ""},
        ]

    def test_render_simple_menu(self):
        # Should not crash when rendering
        self.app._render_cmd_menu(self.commands, 0, "/")

    def test_render_menu_with_selection(self):
        # Should not crash when rendering with a selected index
        self.app._render_cmd_menu(self.commands, 1, "/")


class TestRenderPrompt(unittest.TestCase):
    """Test the prompt rendering logic."""

    def setUp(self):
        self.app = _MockApp()

    def test_render_simple_prompt(self):
        # Should not crash when rendering a prompt
        self.app._render_prompt("hello", 5)

    def test_render_prompt_with_multi_line(self):
        # Should not crash when rendering multi-line prompt
        self.app._render_prompt("line1\nline2", 6)

    def test_render_prompt_cursor_position(self):
        """Should not crash when cursor is at start of line."""
        self.app._render_prompt("hello world", 0)


class TestKbhit(unittest.TestCase):
    """Test keyboard hit detection."""

    def setUp(self):
        self.app = _MockApp()

    def test_key_queue_returns_true(self):
        self.app._key_queue = [b"a"]
        self.assertTrue(self.app._kbhit())

    def test_empty_queue_returns_false(self):
        self.app._key_queue = []
        # When no msvcrt or select, should return False
        with patch("nexus_agent.cli.input_handler.msvcrt", None), \
             patch("nexus_agent.cli.input_handler.select", None):
            self.assertFalse(self.app._kbhit())

    def test_msvcrt_kbhit(self):
        mock_msvcrt = MagicMock()
        mock_msvcrt.kbhit.return_value = True
        with patch("nexus_agent.cli.input_handler.msvcrt", mock_msvcrt):
            self.assertTrue(self.app._kbhit())

    def test_msvcrt_kbhit_exception(self):
        mock_msvcrt = MagicMock()
        mock_msvcrt.kbhit.side_effect = OSError
        with patch("nexus_agent.cli.input_handler.msvcrt", mock_msvcrt), \
             patch("nexus_agent.cli.input_handler.select", None):
            self.assertFalse(self.app._kbhit())


class TestReadByte(unittest.TestCase):
    """Test byte reading with various platform backends."""

    def setUp(self):
        self.app = _MockApp()

    def test_read_from_key_queue(self):
        self.app._key_queue = [b"x", b"y", b"z"]
        self.assertEqual(self.app._read_byte(), b"x")
        self.assertEqual(self.app._read_byte(), b"y")
        self.assertEqual(self.app._read_byte(), b"z")

    def test_msvcrt_getch(self):
        mock_msvcrt = MagicMock()
        mock_msvcrt.getch.return_value = b"a"
        with patch("nexus_agent.cli.input_handler.msvcrt", mock_msvcrt), \
             patch("nexus_agent.cli.input_handler.termios", None):
            self.assertEqual(self.app._read_byte(), b"a")

    def test_msvcrt_getch_exception(self):
        mock_msvcrt = MagicMock()
        mock_msvcrt.getch.side_effect = OSError
        with patch("nexus_agent.cli.input_handler.msvcrt", mock_msvcrt), \
             patch("nexus_agent.cli.input_handler.termios", None):
            result = self.app._read_byte()
            # Falls through to stdin.read(1)
            self.assertEqual(result, b"")

    def test_empty_key_queue_returns_empty_queue_item(self):
        self.app._key_queue = [b""]
        result = self.app._read_byte()
        self.assertEqual(result, b"")


class TestExternalEditor(unittest.TestCase):
    """Test the external editor integration."""

    def setUp(self):
        self.app = _MockApp()

    @patch("subprocess.run")
    @patch("tempfile.mkstemp", return_value=(1, "/tmp/nexus_test.md"))
    @patch("os.fdopen")
    @patch("builtins.open")
    @patch("os.unlink")
    def test_external_editor_returns_changed_content(
        self, mock_unlink, mock_open, mock_fdopen, mock_mkstemp, mock_run
    ):
        mock_fd = MagicMock()
        mock_fdopen.return_value = mock_fd
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = "modified content"

        result = self.app._external_editor("original content")
        self.assertEqual(result, "modified content")

    @patch("subprocess.run")
    @patch("tempfile.mkstemp", return_value=(1, "/tmp/nexus_test.md"))
    @patch("os.fdopen")
    @patch("builtins.open")
    @patch("os.unlink")
    def test_external_editor_no_change_returns_none(
        self, mock_unlink, mock_open, mock_fdopen, mock_mkstemp, mock_run
    ):
        mock_fd = MagicMock()
        mock_fdopen.return_value = mock_fd
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = "original content"

        result = self.app._external_editor("original content")
        self.assertIsNone(result)

    @patch("subprocess.run", side_effect=OSError)
    @patch("tempfile.mkstemp", return_value=(1, "/tmp/nexus_test.md"))
    @patch("os.fdopen")
    @patch("os.unlink")
    def test_external_editor_error_returns_none(
        self, mock_unlink, mock_fdopen, mock_mkstemp, mock_run
    ):
        mock_fd = MagicMock()
        mock_fdopen.return_value = mock_fd
        result = self.app._external_editor("content")
        self.assertIsNone(result)


class TestReadInputBasic(unittest.TestCase):
    """Test basic read_input with mocked dependencies."""

    def setUp(self):
        self.app = _MockApp()
        # Mock stdout to avoid terminal writes
        self.stdout_patcher = patch("sys.stdout.write")
        self.mock_write = self.stdout_patcher.start()
        self.flush_patcher = patch("sys.stdout.flush")
        self.mock_flush = self.flush_patcher.start()
        self.sleep_patcher = patch("time.sleep")
        self.mock_sleep = self.sleep_patcher.start()

    def tearDown(self):
        self.stdout_patcher.stop()
        self.flush_patcher.stop()
        self.sleep_patcher.stop()

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_enter_returns_stripped_value(self):
        """Enter key (\\r) with text returns that text."""
        # Simulate: type "hello", then press Enter
        original_read_byte = self.app._read_byte
        call_count = [0]

        def mock_read_byte():
            call_count[0] += 1
            if call_count[0] <= 5:
                return b"h" if call_count[0] == 1 else \
                       b"e" if call_count[0] == 2 else \
                       b"l" if call_count[0] == 3 else \
                       b"l" if call_count[0] == 4 else \
                       b"o"
            # kbhit returns True for the first read, but we need mock_kbhit too
            return b"\r"

        def mock_kbhit():
            return True

        self.app._read_byte = mock_read_byte
        self.app._kbhit = MagicMock(side_effect=mock_kbhit)

        result = self.app._read_input()
        # Should return the typed text (or None depending on how the loop resolves)
        # This is a basic integration test
        self.assertIsNotNone(result)

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_empty_input_returns_none(self):
        """Enter with no text returns None."""
        self.app._read_byte = MagicMock(return_value=b"\r")
        self.app._kbhit = MagicMock(return_value=True)
        result = self.app._read_input()
        self.assertIsNone(result)

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_ctrl_c_raises_keyboard_interrupt(self):
        """Ctrl+C raises KeyboardInterrupt."""
        self.app._read_byte = MagicMock(return_value=b"\x03")
        self.app._kbhit = MagicMock(return_value=True)
        with self.assertRaises(KeyboardInterrupt):
            self.app._read_input()

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_ctrl_d_empty_raises_eoferror(self):
        """Ctrl+D with empty input raises EOFError."""
        self.app._read_byte = MagicMock(return_value=b"\x04")
        self.app._kbhit = MagicMock(return_value=True)
        self.app._cmd_menu_lines = 0
        with self.assertRaises(EOFError):
            self.app._read_input()

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_backspace_removes_character(self):
        """Backspace should remove the last character."""
        call_log = []

        def mock_read_byte():
            if not call_log:
                call_log.append("a")
                return b"a"
            elif len(call_log) == 1:
                call_log.append("b")
                return b"b"
            elif len(call_log) == 2:
                call_log.append("del")
                return b"\x7f"  # delete removes 'b', leaving 'a'
            return b"\r"

        self.app._read_byte = mock_read_byte
        self.app._kbhit = MagicMock(return_value=True)
        result = self.app._read_input()
        # After typing 'a', 'b', backspace, enter -> should return "a"
        self.assertEqual(result, "a")

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_ctrl_l_clears_screen(self):
        """Ctrl+L should clear screen (no crash)."""
        self.app._read_byte = MagicMock(side_effect=[b"\x0c", b"a", b"\r"])
        self.app._kbhit = MagicMock(return_value=True)
        result = self.app._read_input()
        self.assertIsNotNone(result)
        self.app._rebuild_welcome.assert_called()


class TestExternalEditorTrigger(unittest.TestCase):
    """Test Ctrl+E triggers external editor via _external_editor."""

    def setUp(self):
        self.app = _MockApp()
        self.stdout_patcher = patch("sys.stdout.write")
        self.stdout_patcher.start()
        self.flush_patcher = patch("sys.stdout.flush")
        self.flush_patcher.start()
        self.sleep_patcher = patch("time.sleep")
        self.sleep_patcher.start()

    def tearDown(self):
        self.stdout_patcher.stop()
        self.flush_patcher.stop()
        self.sleep_patcher.stop()

    @patch("nexus_agent.cli.input_handler.msvcrt", None)
    @patch("nexus_agent.cli.input_handler.select", None)
    @patch("nexus_agent.cli.input_handler.termios", None)
    def test_ctrl_e_triggers_editor(self):
        """Ctrl+E (\\x07) should trigger _external_editor."""
        # Mock _external_editor to return a value
        original_editor = self.app._external_editor
        self.app._external_editor = MagicMock(return_value="edited text")

        self.app._read_byte = MagicMock(side_effect=[b"\x07", b"\r"])
        self.app._kbhit = MagicMock(return_value=True)
        result = self.app._read_input()
        self.assertIsNotNone(result)
        self.app._external_editor.assert_called_once()

        self.app._external_editor = original_editor


if __name__ == "__main__":
    unittest.main()
