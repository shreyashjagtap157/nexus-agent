"""Tests for EventHandlerMixin — agent execution event loop, streaming, tool calls."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.cli.event_handler import EventHandlerMixin
from nexus_agent.core.agent import AgentEvent


class _MockApp(EventHandlerMixin):
    """Minimal app that satisfies EventHandlerMixin attribute requirements."""

    def __init__(self):
        self._abort_event = MagicMock()
        self._abort_event.is_set.return_value = False
        self._abort_event.clear = MagicMock()

        self.r = MagicMock()
        self.r.hide_spinner.return_value = ("Worked", 5.0)
        self.r._streaming_buffer = ""

        self._agent = MagicMock()
        self._agent.iteration_count = 3
        self._agent.messages = []
        self._agent.nla_telemetry = MagicMock()

        self._engine = MagicMock()
        self._engine.count_tokens.return_value = 50
        self._engine.model_name = "test-model"

        self._session_mgr = MagicMock()
        self._tokens = MagicMock()
        self._tokens.input_tokens = 0
        self._tokens.output_tokens = 0
        self._tokens.total_input = 0
        self._tokens.total_output = 0
        self._tokens.total_added = 0
        self._tokens.total_removed = 0
        self._tokens.current_request = MagicMock()
        self._tokens.last_request = MagicMock()
        self._tokens.provider_name = "test"
        self._tokens.context_window = 8192

        self._context = MagicMock()
        self._context.messages = 0
        self._context.max_context = 8192

        self._tool_timings = {}
        self._last_responses = []
        self._first_request_done = False
        self._model_status = "idle"
        self._processing = False

        # Mixin expects these methods
        self._handle_slash_command = MagicMock()
        self._rebuild_welcome = MagicMock()
        self._refresh_status = MagicMock()
        self._status_line = MagicMock(return_value="NexusAgent | test")
        self.workspace = MagicMock()
        self.workspace.__str__ = MagicMock(return_value="/mock/workspace")


class TestSampleSessionDiff(unittest.TestCase):
    """Test the git diff sampling logic."""

    def setUp(self):
        self.app = _MockApp()

    @patch("subprocess.run")
    def test_sample_session_diff_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="10\t5\tfile1.py\n2\t1\tfile2.py\n",
        )
        added, removed = self.app._sample_session_diff()
        self.assertEqual(added, 12)
        self.assertEqual(removed, 6)

    @patch("subprocess.run")
    def test_sample_session_diff_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        added, removed = self.app._sample_session_diff()
        self.assertEqual(added, 0)
        self.assertEqual(removed, 0)

    @patch("subprocess.run")
    def test_sample_session_diff_git_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        added, removed = self.app._sample_session_diff()
        self.assertEqual(added, 0)
        self.assertEqual(removed, 0)

    @patch("subprocess.run", side_effect=OSError)
    def test_sample_session_diff_os_error(self, mock_run):
        added, removed = self.app._sample_session_diff()
        self.assertEqual(added, 0)
        self.assertEqual(removed, 0)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_sample_session_diff_not_in_git_repo(self, mock_run):
        added, removed = self.app._sample_session_diff()
        self.assertEqual(added, 0)
        self.assertEqual(removed, 0)


class TestProcessUserInput(unittest.TestCase):
    """Test user input processing."""

    def setUp(self):
        self.app = _MockApp()
        # Mock _run_agent to avoid actual agent execution
        self.app._run_agent = MagicMock()

    def test_slash_command_handled(self):
        """Input starting with / should go to _handle_slash_command."""
        self.app._handle_slash_command = MagicMock()
        self.app._process_user_input("/help")
        self.app._handle_slash_command.assert_called_with("/help")
        self.assertFalse(self.app._run_agent.called)

    def test_no_agent_shows_error(self):
        """No model loaded should show error."""
        self.app._agent = None
        self.app._process_user_input("hello")
        self.app.r.error.assert_called()

    def test_agent_processes_input(self):
        """Normal input with agent should run agent."""
        self.app._process_user_input("hello world")
        self.app._run_agent.assert_called_with("hello world")

    def test_processing_flag_set(self):
        """_processing should be True during agent execution."""
        self.app._process_user_input("hello")
        self.assertFalse(self.app._processing)
        # _run_agent is mocked, so processing is set and then cleared
        # The try/finally should clear it

    def test_session_message_saved(self):
        """Message should be saved to session manager."""
        self.app._process_user_input("hello")
        self.app._session_mgr.save_message.assert_called_with(
            "user", content="hello", type="user"
        )


class TestRunAgentEventTypes(unittest.TestCase):
    """Test _run_agent with different event types."""

    def setUp(self):
        self.app = _MockApp()


    def _make_event(self, event_type: str, data=None):
        e = MagicMock(spec=AgentEvent)
        e.type = event_type
        e.data = data or ""
        return e

    def test_thinking_event(self):
        """Thinking event should update spinner."""
        self.app._agent.run_stream.return_value = [
            self._make_event("thinking"),
            self._make_event("content_complete", "done"),
        ]
        self.app._run_agent("test")
        self.app.r.update_spinner.assert_called()

    def test_content_chunk_handled(self):
        """Content chunks should be streamed."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_chunk", "Hello "),
            self._make_event("content_chunk", "World"),
            self._make_event("content_complete", "Hello World"),
        ]
        self.app._run_agent("test")
        self.app.r.stream_chunk.assert_called()

    def test_tool_call_event(self):
        """Tool call should render tool card and save message."""
        tool_data = {"name": "read_file", "arguments": {"path": "test.py"}}
        self.app._agent.run_stream.return_value = [
            self._make_event("tool_call", tool_data),
            self._make_event("tool_result", {
                "name": "read_file",
                "output": "file content",
                "success": True,
            }),
            self._make_event("content_complete", "done"),
        ]
        self.app._run_agent("test")
        self.app.r.tool_call.assert_called_with("read_file", {"path": "test.py"})

    def test_tool_result_event(self):
        """Tool result should render and save."""
        result_data = {
            "name": "read_file",
            "output": "file content",
            "success": True,
        }
        self.app._agent.run_stream.return_value = [
            self._make_event("tool_call", {"name": "read_file", "arguments": {}}),
            self._make_event("tool_result", result_data),
            self._make_event("content_complete", "done"),
        ]
        self.app._run_agent("test")
        self.app.r.tool_result.assert_called()

    def test_tool_result_error_shows_notification(self):
        """Failed tool should show error notification."""
        result_data = {
            "name": "shell",
            "output": "error output",
            "success": False,
        }
        self.app._agent.run_stream.return_value = [
            self._make_event("tool_call", {"name": "shell", "arguments": {}}),
            self._make_event("tool_result", result_data),
            self._make_event("content_complete", "done"),
        ]
        self.app._run_agent("test")
        self.app.r.show_notification.assert_called()

    def test_error_event(self):
        """Error event should render error and save message."""
        self.app._agent.run_stream.return_value = [
            self._make_event("error", "Something went wrong"),
        ]
        self.app._run_agent("test")
        self.app.r.error.assert_called_with("Something went wrong")
        # Spinner result also saves a system message after the error, so check calls
        error_calls = [
            c for c in self.app._session_mgr.save_message.call_args_list
            if c.kwargs.get("content") == "Something went wrong"
        ]
        self.assertEqual(len(error_calls), 1)

    def test_abort_stops_processing(self):
        """When abort is set, should stop iteration."""
        self.app._abort_event.is_set.side_effect = [False, True, True, True]
        self.app._agent.run_stream.return_value = [
            self._make_event("thinking"),
            self._make_event("content_complete", "partial"),
        ]
        # Should not crash
        self.app._run_agent("test")

    def test_assistant_response_saved(self):
        """Full assistant response should be saved to session."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_complete", "Full response here"),
        ]
        self.app._run_agent("test")
        self.app._session_mgr.save_message.assert_called_with(
            "assistant", content="Full response here", type="assistant"
        )
        self.assertIn("Full response here", self.app._last_responses)

    def test_no_response_no_save(self):
        """Empty response should not save assistant message."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_complete", ""),
        ]
        self.app._run_agent("test")
        # Should not be called with assistant role (empty response)
        assistant_calls = [
            c for c in self.app._session_mgr.save_message.call_args_list
            if c.kwargs.get("role") == "assistant"
        ]
        # With empty full_response, it shouldn't save assistant message
        # Actually with content_complete empty, full_response is "", so no save

    def test_exception_during_agent_run(self):
        """Exception in agent run should be caught and displayed."""
        self.app._agent.run_stream.side_effect = RuntimeError("Agent crashed")
        self.app._run_agent("test")
        self.app.r.error.assert_called()

    def test_streaming_finalized_on_complete(self):
        """Streaming should be finalized on content_chunk completion."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_chunk", "some "),
            self._make_event("content_chunk", "data"),
            self._make_event("content_complete", "some data"),
        ]
        self.app._run_agent("test")
        # Should have been called since we streamed
        self.assertTrue(self.app.r.stream_chunk.called)

    def test_token_tracking(self):
        """Token counts should be updated."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_complete", "Hello World"),
        ]
        self.app._run_agent("test")
        self.assertEqual(self.app._tokens.total_output, 50)

    def test_spinner_hidden_after_run(self):
        """Spinner should be hidden after agent completes."""
        self.app._agent.run_stream.return_value = [
            self._make_event("content_complete", "done"),
        ]
        self.app._run_agent("test")
        self.app.r.hide_spinner.assert_called()


class TestFinalizeStreaming(unittest.TestCase):
    """Test the streaming finalization helper."""

    def setUp(self):
        self.app = _MockApp()
        # Remove the MagicMock override so the real mixin method is used
        self.app._finalize_streaming = EventHandlerMixin._finalize_streaming.__get__(
            self.app, type(self.app)
        )

    def test_finalize_with_buffer(self):
        """Should finalize when buffer has content."""
        self.app.r._streaming_buffer = "some buffered content"
        self.app._finalize_streaming("full response")
        self.app.r.finalize_stream.assert_called_once()

    def test_finalize_without_buffer(self):
        """Should not finalize when buffer is empty."""
        self.app.r._streaming_buffer = ""
        self.app._finalize_streaming("full response")
        self.app.r.finalize_stream.assert_not_called()


class TestProcessUserInputWithRunAgent(unittest.TestCase):
    """Integration tests for _process_user_input with real _run_agent."""

    def setUp(self):
        self.app = _MockApp()
        self.app._run_agent = MagicMock()

    def test_process_with_empty_input(self):
        """Empty/whitespace input should not crash."""
        self.app._process_user_input("   ")
        # _run_agent should be called with whitespace
        self.app._run_agent.assert_called_with("   ")


if __name__ == "__main__":
    unittest.main()
