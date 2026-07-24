"""Session slash commands — /session, /fork, /resume, /background, /sessions, etc.

Extracted from the monolithic command_dispatcher.py to reduce file size
and group session-related logic together.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from nexus_agent.cli.renderer import TokenUsage


class SessionCommandsMixin:
    """Mixin providing session-management slash command handlers."""

    def _cmd_clear(self, args: str):
        if self._agent:
            self._agent.clear_history()
        self._tokens = TokenUsage()
        self.r.clear()
        self.r.system_message("Cleared.")

    def _cmd_session(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return

        parts = args.strip().split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "list":
            try:
                sessions = self._session_mgr.list_sessions()
                if sessions:
                    from rich.table import Table
                    table = Table(title="Sessions", show_header=True, header_style="bold magenta")
                    table.add_column("ID", style="cyan")
                    table.add_column("Created", style="green")
                    table.add_column("Messages", justify="right", style="yellow")
                    table.add_column("Model", style="dim")
                    for s in sessions:
                        table.add_row(s["id"][:12], s["created"], str(s.get("message_count", 0)), s.get("model", ""))
                    self.console.print(table)
                else:
                    self.r.system_message("No saved sessions.")
            except Exception as e:
                self.r.error(f"Failed to list sessions: {e}")

        elif subcmd == "resume" and len(parts) >= 2:
            sid = parts[1].strip()
            self._cmd_resume(sid)

        elif subcmd == "new":
            self._session_id = self._session_mgr.create_session(
                model=self._engine.model_name if self._engine else "unknown",
                provider=self._provider_name or "local",
                workspace=str(self.workspace),
                mode=self._current_mode.value,
            )
            if self._agent:
                self._agent.clear_history()
            self._tokens = TokenUsage()
            self.r.clear()
            self.r.system_message(f"Started new session: {self._session_id}")
            self._rebuild_welcome()

        else:
            try:
                act = self._session_mgr.get_active_session()
                if act:
                    self.console.print(f"  Active Session ID: {act.get('id', 'unknown')}")
                    self.console.print(f"  Title:            {act.get('title', '')}")
                    self.console.print(f"  Workspace:        {act.get('workspace', '')}")
                    self.console.print(f"  Model:            {act.get('model', '')}")
                    self.console.print(f"  Provider:         {act.get('provider', '')}")
                else:
                    self.r.system_message("No active session.")
            except Exception as e:
                self.r.system_message(f"No active session info available: {e}")

    def _cmd_checkpoint(self, args: str):
        if self._session_mgr:
            files = [str(f) for f in self.workspace.rglob("*.py")][:20]
            cp_id = self._session_mgr.create_checkpoint(files, description=args or "Manual checkpoint")
            self.r.system_message(f"Checkpoint: {cp_id[:12]}…")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_checkpoints(self, args: str):
        if self._checkpoint_mgr:
            try:
                checkpoints = self._checkpoint_mgr.list_checkpoints()
                if not checkpoints:
                    self.r.system_message("No checkpoints.")
                    return
                for cp in checkpoints[:10]:
                    self.console.print(f"  [{cp['id'][:12]}] {cp.get('description', '')}  [dim]{cp.get('created', '')}[/dim]")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"Checkpoints: {e}")
        else:
            self.r.system_message("Checkpoint manager unavailable.")

    def _cmd_rollback(self, args: str):
        if self._session_mgr:
            try:
                results = self._session_mgr.rollback(args or None)
                for k, v in results.items():
                    self.console.print(f"  {k}: {v}")
            except ValueError as e:
                self.r.error(str(e))
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_export(self, args: str):
        # Validate path stays within workspace to prevent traversal
        if args:
            requested = Path(args).resolve()
            if not str(requested).startswith(str(self.workspace.resolve())):
                filename = f"nexus-session-{int(time.time())}.json"
                path = self.workspace / filename
            else:
                path = requested
        else:
            filename = f"nexus-session-{int(time.time())}.json"
            path = self.workspace / filename
        if self._session_mgr:
            try:
                data = self._session_mgr.export_session()
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                self.r.system_message(f"Session exported: {path}")
            except (ValueError, OSError, TypeError) as e:
                self.r.error(f"Export: {e}")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_import(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        src = Path(args.strip()) if args else None
        if not src or not args:
            self.r.system_message("Usage: /import <path-to-session.json>")
            return
        if not src.exists():
            self.r.error(f"File not found: {src}")
            return
        try:
            new_id = self._session_mgr.import_session(src)
            if new_id:
                self.r.system_message(f"Imported session: {new_id}")
                self.r.system_message("Run /resume " + new_id[:12] + " to switch to it.")
        except (ValueError, OSError, TypeError, FileNotFoundError) as e:
            self.r.error(f"Import failed: {e}")

    def _cmd_fork(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        title = args.strip() if args else None
        new_id = self._session_mgr.fork_session(title)
        if new_id:
            self.r.system_message(f"Forked session: {new_id[:12]}...")
            self.r.system_message("Run /resume " + new_id[:12] + " to switch to it.")
        else:
            self.r.error("Fork failed (no active session?).")

    def _cmd_resume(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        if args:
            try:
                data = self._session_mgr.resume_session(args)
                if data:
                    self._session_id = data["id"]
                    model = data.get("model")
                    provider = data.get("provider")
                    mode_str = data.get("mode")
                    if mode_str:
                        try:
                            from nexus_agent.core.agent import AgentMode
                            self._current_mode = AgentMode(mode_str)
                            if self._agent:
                                self._agent.mode = self._current_mode
                        except ValueError:
                            pass
                    self.r.system_message(f"Resumed session: {self._session_id}")
                    if model and model != "unknown":
                        if provider == "local" and os.path.isfile(model):
                            self._model_path = model
                            self._provider_name = "local"
                            self._model_status = "loading"
                            self._init_engine(skip_interactive=True)
                            self._init_agent()
                        elif provider != "local":
                            self._provider_name = provider
                            self._model_path = model
                            self._model_status = "loading"
                            self._init_engine(skip_interactive=True)
                            self._init_agent()
                    self._rebuild_welcome()
                else:
                    self.r.error(f"Session not found: {args}")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"Resume failed: {e}")
        else:
            try:
                sessions = self._session_mgr.list_sessions()
                if sessions:
                    items = [(f"{s.get('id', '?')[:16]}  {s.get('name', '')}", s['id']) for s in sessions[:10]]
                    sel = self._interactive_menu(items, "Select session to resume:")
                    if sel:
                        self._cmd_resume(sel)
                else:
                    self.r.system_message("No saved sessions.")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.error(f"List sessions: {e}")

    def _cmd_rename(self, args: str):
        if self._session_mgr:
            try:
                self._session_mgr.rename(args.strip())
                self.r.system_message(f"Session renamed: {args.strip()}")
            except (ValueError, OSError, RuntimeError) as e:
                self.r.system_message(f"Rename: {e}")
        else:
            self.r.system_message("Session manager unavailable.")

    def _cmd_copy(self, args: str):
        """Copy to clipboard. Usage: /copy [last|N|session|<text>]."""
        try:
            import pyperclip
        except ImportError:
            self.r.system_message("pyperclip not installed — cannot copy. Try `pip install pyperclip`.")
            return
        text = ""
        if not args or args == "last":
            text = self._copied_text or (
                self._last_responses[0] if getattr(self, "_last_responses", []) else ""
            )
            if not text:
                self.r.system_message("Nothing to copy.")
                return
            pyperclip.copy(text)
            self.r.system_message("Copied last response.")
        elif args == "session":
            if self._agent:
                history = self._agent.get_conversation_history()
                text = json.dumps(history, indent=2)
                pyperclip.copy(text)
                self.r.system_message(f"Copied session ({len(history)} messages).")
            else:
                self.r.system_message("No active session.")
        elif args.isdigit():
            n = int(args)
            if self._agent and 0 < n <= len(self._agent.messages):
                msg = self._agent.messages[-n]
                pyperclip.copy(msg.content or "")
                self.r.system_message(f"Copied message -{n}.")
            else:
                self.r.system_message("Invalid message index.")
        else:
            pyperclip.copy(args)
            self.r.system_message("Copied.")
        self._copied_text = ""

    def _cmd_add_dir(self, args: str):
        """Add a directory to the session (per-request only — does not persist)."""
        target = Path(args).expanduser().resolve() if args else None
        if not target:
            self.r.system_message("Usage: /add-dir <path>")
            return
        if not target.is_dir():
            self.r.error(f"Not a directory: {target}")
            return
        if not str(target).startswith(str(self.workspace.resolve())) and not args.startswith("~"):
            self.r.system_message(
                f"Note: {target} is outside the workspace {self.workspace}"
            )
        self._extra_dirs = getattr(self, "_extra_dirs", []) + [target]
        self.r.system_message(f"Added dir: {target} (in-session only)")

    def _cmd_rewind(self, args: str):
        """Rewind to the latest checkpoint (or a specific id)."""
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        try:
            target = args.strip() if args else None
            results = self._session_mgr.rollback(target)
            for k, v in results.items():
                self.console.print(f"  {k}: {v}")
            if self._agent:
                self._agent.clear_history()
        except (ValueError, OSError, RuntimeError) as e:
            self.r.error(f"Rewind failed: {e}")

    def _cmd_background(self, args: str):
        """Run a prompt in a parallel isolated session."""
        if not self._agent or not self._engine:
            self.r.system_message("No model loaded.")
            return
        if not args:
            self.r.system_message("Usage: /background <prompt>")
            return
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        from nexus_agent.session.background import BackgroundSession

        def run_in_background(prompt: str) -> str:
            from nexus_agent.core.agent import AgentEventType
            out: list[str] = []
            for ev in self._agent.run(prompt):
                if ev.type == AgentEventType.CONTENT_COMPLETE and isinstance(ev.data, str):
                    out.append(ev.data)
                elif ev.type == AgentEventType.CONTENT and isinstance(ev.data, str):
                    out.append(ev.data)
                elif ev.type == AgentEventType.ERROR:
                    out.append(f"\n[error] {ev.data}")
            return "".join(out).strip()

        bg = BackgroundSession(
            prompt=args,
            run_callable=run_in_background,
        )
        bg_id = bg.start()
        self._session_mgr.register_background(bg)
        self.r.system_message(f"Background session started: {bg_id} (use /sessions to view)")

    def _cmd_sessions(self, args: str):
        """Interactive session picker — list, search, and resume."""
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        sub = args.strip().split(maxsplit=1) if args else []
        subcmd = sub[0].lower() if sub else ""

        if subcmd == "list":
            try:
                sessions = self._session_mgr.list_sessions(limit=50)
            except (OSError, ValueError, RuntimeError) as e:
                self.r.error(f"List failed: {e}")
                return
            if not sessions:
                self.r.system_message("No saved sessions.")
                return
            from rich.table import Table
            tbl = Table(title="Sessions", show_header=True, header_style="bold magenta")
            tbl.add_column("ID", style="cyan")
            tbl.add_column("Title", style="green", max_width=40)
            tbl.add_column("Messages", justify="right", style="yellow")
            tbl.add_column("Updated", style="dim")
            for s in sessions:
                tbl.add_row(
                    s.get("id", "?")[:12],
                    (s.get("title") or "")[:40],
                    str(s.get("message_count", 0)),
                    s.get("updated", ""),
                )
            self.console.print(tbl)
            return

        if subcmd == "background":
            bgs = self._session_mgr.list_background_sessions()
            if not bgs:
                self.r.system_message("No background sessions.")
                return
            from rich.table import Table
            tbl = Table(title="Background Sessions", show_header=True, header_style="bold magenta")
            tbl.add_column("ID", style="cyan")
            tbl.add_column("State", style="yellow")
            tbl.add_column("Duration", justify="right", style="dim")
            tbl.add_column("Prompt", max_width=60)
            for bg in bgs:
                tbl.add_row(
                    bg.get("session_id", "?")[:12],
                    bg.get("state", "?"),
                    f"{bg.get('duration_s', 0):.1f}s",
                    bg.get("prompt", "")[:60],
                )
            self.console.print(tbl)
            return

        if subcmd == "stop" and len(sub) >= 2:
            bg = self._session_mgr.get_background_session(sub[1])
            if bg and bg.cancel():
                self.r.system_message(f"Cancellation requested for {sub[1]}.")
            else:
                self.r.error(f"No running background session: {sub[1]}")
            return

        # Default: interactive picker
        try:
            sessions = self._session_mgr.list_sessions(limit=50)
        except (OSError, ValueError, RuntimeError) as e:
            self.r.error(f"List failed: {e}")
            return
        if not sessions:
            self.r.system_message("No saved sessions.")
            return
        items = [
            (
                f"{s.get('id', '?')[:12]}  {(s.get('title') or '(untitled)')[:40]}  "
                f"[{s.get('message_count', 0)} msg · {s.get('updated', '')}]",
                s.get("id"),
            )
            for s in sessions
        ]
        sel = self._interactive_menu(items, "Select session to resume (↑↓ Enter Esc):")
        if sel:
            self._cmd_resume(sel)
