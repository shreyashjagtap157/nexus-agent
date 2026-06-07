"""
LSP Transport — Real Language Server Protocol client over stdio (JSON-RPC 2.0).

Implements the LSP wire protocol with Content-Length framed messages so we can talk
to actual language servers (pylsp, pyright, rust-analyzer, gopls, tsserver, etc.)
when installed, and falls back to AST-based introspection when no server is reachable.

This is the transport layer — see ``lsp_client.py`` for the high-level tool surface.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LSPConfig:
    """Per-language server configuration."""

    command: list[str]
    """Executable + args used to spawn the server (e.g. ['pylsp', '--check-parent-process'])."""

    languages: list[str] = field(default_factory=list)
    """File extensions or language ids this server handles (e.g. ['python'])."""

    initialization_options: dict[str, Any] = field(default_factory=dict)
    """Optional LSP initializationOptions payload."""

    env: dict[str, str] = field(default_factory=dict)
    """Extra environment variables to pass to the server process."""


# Sensible default server command table. Tools like pylsp / pyright can be added
# by users through config; these are best-effort lookups used when no config
# is supplied.
DEFAULT_SERVERS: dict[str, LSPConfig] = {
    "python": LSPConfig(
        command=["pylsp"],
        languages=["python", ".py"],
    ),
    "typescript": LSPConfig(
        command=["typescript-language-server", "--stdio"],
        languages=["typescript", "javascript", ".ts", ".tsx", ".js", ".jsx"],
    ),
    "rust": LSPConfig(
        command=["rust-analyzer"],
        languages=["rust", ".rs"],
    ),
    "go": LSPConfig(
        command=["gopls"],
        languages=["go", ".go"],
    ),
}


class LSPError(RuntimeError):
    """Raised on LSP protocol or transport errors."""


class _PendingRequest:
    """Tracks a single in-flight request id and the queue that resolves it."""

    __slots__ = ("id", "event", "result")

    def __init__(self, id: int) -> None:
        self.id = id
        self.event = threading.Event()
        self.result: dict[str, Any] | None = None


class LSPClient:
    """Minimal JSON-RPC 2.0 client for Language Server Protocol servers.

    Spawns a language server subprocess, exchanges framed JSON-RPC messages,
    and exposes ``request`` / ``notify`` helpers. The transport is fully
    thread-safe; one request at a time is awaited by id.

    Example::

        client = LSPClient(LSPConfig(command=["pylsp"]), workspace=Path("."))
        client.start()
        try:
            caps = client.initialize()
            client.did_open("foo.py", "x = 1\\n")
            syms = client.request("textDocument/documentSymbol", {"textDocument": {"uri": "file:///foo.py"}})
        finally:
            client.stop()
    """

    def __init__(
        self,
        config: LSPConfig,
        workspace: Path | None = None,
        server_id: str = "lsp",
        request_timeout: float = 15.0,
    ) -> None:
        self.config = config
        self.server_id = server_id
        self.workspace = (workspace or Path.cwd()).resolve()
        self.request_timeout = request_timeout

        self._proc: subprocess.Popen[bytes] | None = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._id_lock = threading.Lock()
        self._pending: dict[int, _PendingRequest] = {}
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False
        self._server_caps: dict[str, Any] = {}

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Spawn the server subprocess and begin reading messages."""
        if self._started:
            return

        if not self.config.command:
            raise LSPError("LSP config has empty command")

        # If the first item is not an absolute path, search PATH for it.
        cmd = list(self.config.command)
        if not os.path.isabs(cmd[0]) and not Path(cmd[0]).exists():
            resolved = shutil.which(cmd[0])
            if not resolved:
                raise LSPError(
                    f"Language server binary '{cmd[0]}' not found on PATH. "
                    f"Install it (e.g. `pip install python-lsp-server[all]`) or "
                    f"configure a different command via LSPConfig."
                )
            cmd[0] = resolved

        env = os.environ.copy()
        env.update(self.config.env)

        logger.info("[%s] spawning %s", self.server_id, " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.workspace),
                env=env,
                bufsize=0,
            )
        except (OSError, ValueError) as e:
            raise LSPError(f"Failed to spawn language server {cmd!r}: {e}") from e

        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._read_loop, name=f"lsp-reader-{self.server_id}", daemon=True
        )
        self._reader_thread.start()
        self._started = True

    def stop(self) -> None:
        """Send a graceful shutdown and terminate the server."""
        if not self._started:
            return
        self._stop_event.set()
        try:
            # Best-effort: ask server to shut down. We do not raise on failure.
            self.notify("shutdown", {})
            self.notify("exit", {})
        except (LSPError, OSError, ValueError):
            pass

        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except (OSError, ValueError) as e:
                logger.debug("[%s] terminate error: %s", self.server_id, e)
        self._proc = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None
        self._started = False

    def __enter__(self) -> "LSPClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()

    # ------------------------------------------------------------------ public api

    def initialize(self) -> dict[str, Any]:
        """Send ``initialize`` and wait for the server's response.

        Returns the server's ``capabilities`` object. Raises ``LSPError`` if the
        server reports an error or fails to respond.
        """
        params = {
            "processId": os.getpid(),
            "rootUri": self.workspace.as_uri(),
            "capabilities": {
                "workspace": {
                    "workspaceEdit": {"documentChanges": True},
                    "didChangeConfiguration": {"dynamicRegistration": False},
                },
                "textDocument": {
                    "synchronization": {"dynamicRegistration": False, "didSave": True},
                    "completion": {"dynamicRegistration": False},
                    "hover": {"dynamicRegistration": False, "contentFormat": ["markdown", "plaintext"]},
                    "definition": {"dynamicRegistration": False, "linkSupport": True},
                    "references": {"dynamicRegistration": False},
                    "documentSymbol": {"dynamicRegistration": False},
                    "formatting": {"dynamicRegistration": False},
                    "rangeFormatting": {"dynamicRegistration": False},
                    "rename": {"dynamicRegistration": False, "prepareSupport": True},
                    "publishDiagnostics": {"relatedInformation": True},
                },
                "window": {"workDoneProgress": False},
            },
            "initializationOptions": self.config.initialization_options,
            "workspaceFolders": [
                {"uri": self.workspace.as_uri(), "name": self.workspace.name}
            ],
        }
        result = self.request("initialize", params)
        if isinstance(result, dict) and "capabilities" in result:
            self._server_caps = result["capabilities"] or {}
        else:
            self._server_caps = {}
        # Acknowledge initialization per LSP spec
        self.notify("initialized", {})
        return self._server_caps

    @property
    def server_capabilities(self) -> dict[str, Any]:
        return dict(self._server_caps)

    def did_open(self, file_path: str, text: str, language_id: str | None = None) -> None:
        """Notify the server that a file was opened (loads its contents)."""
        uri = self._to_uri(file_path)
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id or self._guess_language_id(file_path),
                    "version": 1,
                    "text": text,
                }
            },
        )

    def did_change(self, file_path: str, text: str, version: int = 2) -> None:
        """Notify the server of a full-document change."""
        self.notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": self._to_uri(file_path), "version": version},
                "contentChanges": [{"text": text}],
            },
        )

    def did_save(self, file_path: str, text: str | None = None) -> None:
        """Notify the server of a save event."""
        params: dict[str, Any] = {"textDocument": {"uri": self._to_uri(file_path)}}
        if text is not None:
            params["text"] = text
        self.notify("textDocument/didSave", params)

    def did_close(self, file_path: str) -> None:
        self.notify("textDocument/didClose", {"textDocument": {"uri": self._to_uri(file_path)}})

    def request(self, method: str, params: Any | None = None) -> Any:
        """Send a JSON-RPC request and wait for the matching response."""
        if not self._started or self._proc is None or self._proc.stdin is None:
            raise LSPError("LSP client not started")

        with self._id_lock:
            req_id = self._next_id
            self._next_id += 1
        pending = _PendingRequest(req_id)
        with self._lock:
            self._pending[req_id] = pending

        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        self._write_message(msg)

        if not pending.event.wait(timeout=self.request_timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise LSPError(f"LSP request '{method}' timed out after {self.request_timeout}s")

        with self._lock:
            self._pending.pop(req_id, None)
        if pending.result is None:
            return None
        if "error" in pending.result:
            err = pending.result["error"]
            raise LSPError(
                f"LSP error from '{method}': {err.get('message')} (code={err.get('code')})"
            )
        return pending.result.get("result")

    def notify(self, method: str, params: Any | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._started or self._proc is None or self._proc.stdin is None:
            return
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        try:
            self._write_message(msg)
        except (OSError, ValueError) as e:
            logger.debug("[%s] notify %s failed: %s", self.server_id, method, e)

    # ------------------------------------------------------------------ internals

    def _write_message(self, msg: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise LSPError("Server stdin closed")
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self._proc.stdin.write(header)
            self._proc.stdin.write(body)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as e:
            raise LSPError(f"Failed to write to language server: {e}") from e

    def _read_loop(self) -> None:
        """Continuously read framed messages and dispatch responses/notifications."""
        assert self._proc is not None and self._proc.stdout is not None
        stream = self._proc.stdout
        try:
            while not self._stop_event.is_set():
                msg = self._read_one_message(stream)
                if msg is None:
                    break
                self._dispatch(msg)
        except (OSError, ValueError, UnicodeDecodeError) as e:
            logger.debug("[%s] reader loop ended: %s", self.server_id, e)

    def _read_one_message(self, stream: Any) -> dict[str, Any] | None:
        """Read one LSP message (headers + JSON body) from the byte stream."""
        headers: dict[str, str] = {}
        # Read headers
        while True:
            line = stream.readline()
            if not line:
                return None
            line = line.decode("ascii", errors="replace").rstrip("\r\n")
            if not line:
                break
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        if "content-length" not in headers:
            return None
        try:
            length = int(headers["content-length"])
        except ValueError:
            return None
        body = b""
        remaining = length
        while remaining > 0:
            chunk = stream.read(remaining)
            if not chunk:
                return None
            body += chunk
            remaining -= len(chunk)
        try:
            return json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None

    def _dispatch(self, msg: dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            req_id = msg["id"]
            with self._lock:
                pending = self._pending.get(req_id)
            if pending is not None:
                pending.result = msg
                pending.event.set()
            return
        # Notifications (window/logMessage, textDocument/publishDiagnostics, etc.)
        method = msg.get("method")
        if method == "window/logMessage":
            params = msg.get("params", {}) or {}
            logger.info("[%s] log: %s", self.server_id, params.get("message"))
        elif method == "textDocument/publishDiagnostics":
            # Diagnostics are surfaced via ``request('textDocument/diagnostic')`` when needed.
            pass

    @staticmethod
    def _to_uri(file_path: str) -> str:
        p = Path(file_path).resolve()
        return p.as_uri()

    def _guess_language_id(self, file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
        }.get(suffix, "plaintext")


class LSPClientPool:
    """Manages one ``LSPClient`` per language and starts servers on demand."""

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self._clients: dict[str, LSPClient] = {}
        self._lock = threading.Lock()
        self._custom_configs: dict[str, LSPConfig] = {}

    def register(self, language: str, config: LSPConfig) -> None:
        """Register or override a server config for a language."""
        with self._lock:
            self._custom_configs[language.lower()] = config
            # Stop any cached client using the old config
            existing = self._clients.get(language.lower())
            if existing:
                existing.stop()
                self._clients.pop(language.lower(), None)

    def get(self, file_path: str) -> LSPClient | None:
        """Return a started client for the file's language, or ``None`` if unavailable.

        Returns ``None`` (rather than raising) when no server command resolves —
        callers should fall back to AST-based introspection in that case.
        """
        lang = Path(file_path).suffix.lower().lstrip(".")
        if not lang:
            return None
        return self._ensure(lang)

    def shutdown(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for c in clients:
            try:
                c.stop()
            except (LSPError, OSError, ValueError):
                pass

    def _ensure(self, language: str) -> LSPClient | None:
        with self._lock:
            cached = self._clients.get(language)
            if cached is not None and cached._started:
                return cached
            config = self._custom_configs.get(language)
            if config is None:
                # try default mapping
                for key, default in DEFAULT_SERVERS.items():
                    if language in default.languages or f".{language}" in default.languages:
                        config = default
                        break
            if config is None:
                return None
            client = LSPClient(config=config, workspace=self.workspace, server_id=language)
            try:
                client.start()
            except LSPError as e:
                logger.info("LSP server for %s unavailable: %s", language, e)
                return None
            try:
                client.initialize()
            except LSPError as e:
                logger.info("LSP init for %s failed: %s", language, e)
                client.stop()
                return None
            self._clients[language] = client
            return client

    def __enter__(self) -> "LSPClientPool":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.shutdown()
