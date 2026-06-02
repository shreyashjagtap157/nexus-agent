"""Event handler — user input processing and agent execution loop."""

from __future__ import annotations

import logging
import random
import time

from nexus_agent.cli.renderer import SPINNER_VERBS_PRESENT

logger = logging.getLogger(__name__)


class EventHandlerMixin:
    """Mixin that provides user input processing and agent execution event loop."""

    def _process_user_input(self, user_input: str):
        self._abort_event.clear()

        if user_input.startswith("/"):
            self._handle_slash_command(user_input)
            return

        if not self._agent:
            self.r.error("No model loaded. Use --model or set NEXUS_MODEL_PATH.")
            return

        in_tokens = self._engine.count_tokens(user_input) if self._engine else len(user_input.split())
        self._tokens.input_tokens += in_tokens
        self._tokens.total_input += in_tokens
        self._tokens.current_request.input_tokens = in_tokens

        if self._session_mgr:
            self._session_mgr.save_message("user", content=user_input)
            try:
                self._session_mgr.auto_title(user_input)
            except (OSError, ValueError):
                pass

        self._processing = True
        self._run_agent(user_input)
        self._processing = False
        if not self._first_request_done:
            self._first_request_done = True
            self._model_status = "loaded"
            self._rebuild_welcome()

    def _run_agent(self, user_input: str):
        full_response = ""
        verb = random.choice(SPINNER_VERBS_PRESENT)
        self.r.show_spinner(verb)
        _streaming_started = False
        self._tokens.current_request.begin()

        try:
            for event in self._agent.run_stream(user_input):
                if self._abort_event.is_set():
                    break

                if event.type == "thinking":
                    new_verb = random.choice(SPINNER_VERBS_PRESENT)
                    self.r.update_spinner(new_verb)

                elif event.type == "content":
                    full_response = event.data

                elif event.type == "content_chunk":
                    if not _streaming_started:
                        self.r.hide_spinner()
                        _streaming_started = True
                    self.r.stream_chunk(event.data)
                    full_response += event.data

                elif event.type == "content_complete":
                    full_response = event.data
                    if isinstance(event.data, str):
                        out_tokens = self._engine.count_tokens(event.data) if self._engine else len(event.data.split())
                        self._tokens.output_tokens += out_tokens
                        self._tokens.total_output += out_tokens
                        self._tokens.current_request.output_tokens = out_tokens

                elif event.type == "tool_call":
                    self._finalize_streaming(full_response)
                    if _streaming_started:
                        full_response = ""
                        _streaming_started = False
                    self.r.hide_spinner()
                    name = event.data["name"]
                    args = event.data.get("arguments", {})
                    self.r.tool_call(name, args)
                    self._tool_timings[name] = time.time()
                    tverb = random.choice([
                        "Reading", "Writing", "Searching", "Executing",
                        "Fetching", "Parsing", "Grepping", "Editing",
                    ])
                    self.r.show_spinner(tverb)

                elif event.type == "tool_result":
                    self.r.hide_spinner()
                    name = event.data.get("name", "")
                    output = event.data.get("output", "")
                    success = event.data.get("success", True)
                    elapsed = time.time() - self._tool_timings.pop(name, time.time())
                    self.r.tool_result(name, output, success, elapsed)
                    self.r.show_spinner(random.choice(SPINNER_VERBS_PRESENT))

                elif event.type == "error":
                    self._finalize_streaming(None)
                    if _streaming_started:
                        _streaming_started = False
                    self.r.hide_spinner()
                    self.r.error(str(event.data))

                self._refresh_status()

        except (RuntimeError, ValueError, OSError) as ex:
            logger.exception("Agent execution failed")
            self._finalize_streaming(None)
            if _streaming_started:
                _streaming_started = False
            self.r.hide_spinner()
            self.r.error(f"Execution failed: {ex}")
            return

        result = self.r.hide_spinner()

        if result and not self._abort_event.is_set():
            past_verb, elapsed = result
            past_verb = past_verb or "Worked"
            if elapsed < 1:
                elapsed_str = f"{elapsed:.1f}s"
            elif elapsed < 60:
                elapsed_str = f"{elapsed:.0f}s"
            else:
                elapsed_str = f"{elapsed / 60:.0f}m {elapsed % 60:.0f}s"
            self.r.system_message(f"{past_verb} for {elapsed_str}")

        self._finalize_streaming(full_response)
        if _streaming_started:
            _streaming_started = False
        elif full_response and not self._abort_event.is_set():
            self.r.assistant_message(full_response)

        if full_response and not self._abort_event.is_set():
            if self._session_mgr:
                self._session_mgr.save_message("assistant", content=full_response)

            self._tokens.current_request.end()
            in_r = self._tokens.current_request.input_tokens
            out_r = self._tokens.current_request.output_tokens
            if self._tokens.current_request.elapsed > 0 or in_r or out_r:
                self.r.system_message(self._tokens.display_request())
            self._tokens.last_request.input_tokens = self._tokens.current_request.input_tokens
            self._tokens.last_request.output_tokens = self._tokens.current_request.output_tokens
            self._tokens.last_request.elapsed = self._tokens.current_request.elapsed

        if self._agent and hasattr(self._agent, 'messages'):
            self._context.messages = len(self._agent.messages)
        self._refresh_status()
        self.r.set_terminal_title(self._status_line())

        if full_response and not self._abort_event.is_set():
            self.r.divider()

        if self._abort_event.is_set():
            self._abort_event.clear()

    def _finalize_streaming(self, full_response: str | None):
        """Consolidate duplicate finalize_stream() calls into one path."""
        if hasattr(self.r, '_streaming_buffer') and self.r._streaming_buffer:
            self.r.finalize_stream()
