"""Session slash commands — /session, /resume, /fork, /rename, /export, etc."""

from __future__ import annotations

import json
import time
from pathlib import Path

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.cli.renderer import TokenUsage


class SessionCommands(BaseCommands):
    """Mixin providing session-related slash command handlers."""


    def _cmd_clear(self, args: str):
        if self._agent:
            self._agent.clear_history()
        self._tokens = TokenUsage()
        self.r.clear()
        self.r.system_message("Cleared.")


    def _cmd_session(self, args: str):
        if self._session_mgr:
            try:
                info = self._session_mgr.get_session_info()
                for k, v in info.items():
                    self.console.print(f"  {k}: {v}")
            except (ValueError, OSError, KeyError, TypeError):
                self.r.system_message("No active session.")
        else:
            self.r.system_message("Session manager unavailable.")


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
            # Only allow relative paths (workspace-relative) or explicit safe paths
            if not str(requested).startswith(str(self.workspace.resolve())):
                # If not workspace-relative, use default name in workspace
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


    def _cmd_fork(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        new_id = self._session_mgr.fork_session(args.strip() if args else None)
        if new_id:
            self.r.system_message(f"Forked session: {new_id}")
        else:
            self.r.error("Fork failed.")


    def _cmd_resume(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        if args:
            try:
                data = self._session_mgr.resume_session(args)
                if data:
                    self.r.system_message(f"Resumed session: {args}")
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


    def _cmd_import(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        src = Path(args.strip()) if args else None
        if not src:
            self.r.error("Usage: /import <path>")
            return
        if not src.exists():
            self.r.error(f"Path not found: {src}")
            return
        new_id = self._session_mgr.import_session(src)
        if new_id:
            self.r.system_message(f"Imported session: {new_id}")
        else:
            self.r.error("Import failed.")


    def _cmd_copy(self, args: str):
        try:
            import pyperclip
        except ImportError:
            self.r.system_message("pyperclip not installed — cannot copy.")
            return
        if args == "last":
            text = self._copied_text
            if text:
                pyperclip.copy(text)
                self.r.system_message("Copied last response.")
            else:
                self.r.system_message("Nothing to copy.")
        elif args == "session":
            if self._agent:
                history = self._agent.get_conversation_history()
                import json
                text = json.dumps(history, indent=2)
                pyperclip.copy(text)
                self.r.system_message(f"Copied session ({len(history)} messages).")
            else:
                self.r.system_message("No active session.")
        elif args.isdigit():
            n = int(args)
            if self._agent and n <= len(self._agent.messages):
                msg = self._agent.messages[-n]
                pyperclip.copy(msg.content or "")
                self.r.system_message(f"Copied message -{n}.")
            else:
                self.r.system_message("Invalid message index.")
        else:
            pyperclip.copy(args)
            self.r.system_message("Copied.")
        self._copied_text = ""


    def _cmd_rewind(self, args: str):
        if not self._session_mgr:
            self.r.system_message("Session manager unavailable.")
            return
        try:
            target = args.strip() if args else None
            results = self._session_mgr.rollback(target)
            for k, v in results.items():
                self.console.print(f"  {k}: {v}")
        except ValueError as e:
            self.r.error(str(e))
