"""Tests for the LSP transport layer — JSON-RPC framing, request/notify, pool.

The real subprocess tests are in :class:`TestLSPClientSubprocess` and only run
when the ``nexus_run_subprocess_tests`` env var is set, since pytest's output
capture can interfere with stdio-based servers in subtle ways on Windows.
"""

from __future__ import annotations

import json
import os
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from nexus_agent.tools.lsp_transport import (
    DEFAULT_SERVERS,
    LSPClient,
    LSPClientPool,
    LSPConfig,
    LSPError,
)

_RUN_SUBPROC = os.environ.get("nexus_run_subprocess_tests") == "1"


def _sys_executable() -> str:
    import sys as _s
    return _s.executable


class TestLSPConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = LSPConfig(command=["pylsp"])
        self.assertEqual(cfg.command, ["pylsp"])
        self.assertEqual(cfg.languages, [])
        self.assertEqual(cfg.initialization_options, {})
        self.assertEqual(cfg.env, {})

    def test_custom_options(self):
        cfg = LSPConfig(
            command=["pylsp", "--check"],
            languages=["python"],
            initialization_options={"pylsp": {"plugins": {"pyflakes": {"enabled": True}}}},
            env={"FOO": "bar"},
        )
        self.assertEqual(cfg.languages, ["python"])
        self.assertEqual(cfg.env, {"FOO": "bar"})
        self.assertIn("pylsp", cfg.initialization_options)

    def test_default_servers_present(self):
        self.assertIn("python", DEFAULT_SERVERS)
        self.assertIn("typescript", DEFAULT_SERVERS)
        self.assertIn("rust", DEFAULT_SERVERS)
        self.assertIn("go", DEFAULT_SERVERS)


class FakeStdout:
    """Mimics ``proc.stdout`` for the reader loop.

    ``feed`` injects a complete JSON-RPC message that the transport's reader
    should parse and dispatch.
    """

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, msg: dict[str, Any]) -> None:
        body = json.dumps(msg).encode("utf-8")
        self._buf += f"Content-Length: {len(body)}\r\n\r\n".encode() + body

    def readline(self) -> bytes:
        if not self._buf:
            return b""
        idx = self._buf.find(b"\n")
        if idx < 0:
            line, self._buf = self._buf, b""
            return line
        line, self._buf = self._buf[: idx + 1], self._buf[idx + 1 :]
        return line

    def read(self, n: int) -> bytes:
        if n <= 0 or not self._buf:
            return b""
        out, self._buf = self._buf[:n], self._buf[n:]
        return out


class FakeStdin:
    """Captures everything the transport writes to the subprocess."""

    def __init__(self) -> None:
        self.buffer_data: list[bytes] = []
        self._buf = b""

    def write(self, data: bytes) -> int:
        self._buf += data
        # split on \r\n\r\n header terminator and parse header+body
        while b"\r\n\r\n" in self._buf:
            head, rest = self._buf.split(b"\r\n\r\n", 1)
            self._buf = rest
            length = 0
            for line in head.split(b"\r\n"):
                k, _, v = line.decode("ascii", errors="replace").partition(":")
                if k.lower() == "content-length":
                    length = int(v.strip())
            if len(self._buf) < length:
                # wait for more — put it back
                self._buf = b"\r\n\r\n".join([head, self._buf])
                break
            body = self._buf[:length]
            self._buf = self._buf[length:]
            self.buffer_data.append(b"\r\n\r\n".join([head, body]))
        return len(data)

    def flush(self) -> None:
        return None


def _make_started_client(stdout: FakeStdout, stdin: FakeStdin) -> LSPClient:
    """Build a client whose ``_proc`` is a MagicMock driving our fakes."""
    cfg = LSPConfig(command=["fake"])
    client = LSPClient(cfg, workspace=Path("."), server_id="t", request_timeout=2.0)
    proc = MagicMock()
    proc.stdout = stdout
    proc.stdin = stdin
    proc.poll.return_value = None
    client._proc = proc
    client._started = True
    return client


class TestLSPClientFraming(unittest.TestCase):
    """Drive the reader loop with a fake stdout — no real subprocess needed."""

    def _wait_dispatched(self, client: LSPClient, request_id: int,
                          timeout: float = 2.0) -> Any:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with client._lock:
                pending = client._pending.get(request_id)
            if pending is not None and pending.result is not None:
                return pending.result
            time.sleep(0.01)
        raise AssertionError(f"Request {request_id} was never resolved within {timeout}s")

    def test_request_returns_result(self):
        stdout, stdin = FakeStdout(), FakeStdin()
        client = _make_started_client(stdout, stdin)
        stdout.feed({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {"hoverProvider": True}}})

        with client._id_lock:
            req_id = client._next_id
            client._next_id += 1
        pending = type("P", (), {"event": threading.Event(), "result": None})()
        with client._lock:
            client._pending[req_id] = pending

        # Start the reader thread (it will read the response and resolve the request)
        client._reader_thread = threading.Thread(target=client._read_loop, daemon=True)
        client._reader_thread.start()

        # Write the request message through the real transport code path
        msg = {"jsonrpc": "2.0", "id": req_id, "method": "initialize", "params": {}}
        client._write_message(msg)

        pending.event.wait(timeout=2.0)
        self.assertIsNotNone(pending.result)
        self.assertIn("result", pending.result)
        self.assertTrue(pending.result["result"]["capabilities"]["hoverProvider"])
        client._stop_event.set()
        client._reader_thread.join(timeout=1.0)

    def test_request_surfaces_server_error(self):
        stdout, stdin = FakeStdout(), FakeStdin()
        client = _make_started_client(stdout, stdin)

        with client._id_lock:
            req_id = client._next_id
            client._next_id += 1
        pending = type("P", (), {"event": threading.Event(), "result": None})()
        with client._lock:
            client._pending[req_id] = pending

        # Feed the error response *with the matching id* so the dispatcher can
        # resolve the pending request.
        stdout.feed({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}})

        client._reader_thread = threading.Thread(target=client._read_loop, daemon=True)
        client._reader_thread.start()
        client._write_message({"jsonrpc": "2.0", "id": req_id, "method": "x", "params": {}})

        pending.event.wait(timeout=2.0)
        self.assertIsNotNone(pending.result)
        self.assertIn("error", pending.result)
        self.assertEqual(pending.result["error"]["code"], -32601)
        client._stop_event.set()
        client._reader_thread.join(timeout=1.0)

    def test_timeout_raises_lsp_error(self):
        stdout, stdin = FakeStdout(), FakeStdin()
        client = _make_started_client(stdout, stdin)
        client.request_timeout = 0.2
        with self.assertRaises(LSPError) as ctx:
            client.request("textDocument/hover", {})
        self.assertIn("timed out", str(ctx.exception))

    def test_notify_does_not_require_response(self):
        stdout, stdin = FakeStdout(), FakeStdin()
        client = _make_started_client(stdout, stdin)
        # Should not raise even with no reader thread; the call is fire-and-forget
        client.notify("textDocument/didOpen", {"x": 1})
        self.assertTrue(len(stdin.buffer_data) >= 1 or stdin._buf)

    def test_start_raises_for_missing_binary(self):
        with patch("shutil.which", return_value=None):
            client = LSPClient(
                LSPConfig(command=["definitely-not-installed-server"]),
                workspace=Path("."),
                server_id="t",
            )
            with self.assertRaises(LSPError) as ctx:
                client.start()
            self.assertIn("not found", str(ctx.exception))


class TestLSPClientPool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(os.environ.get("TEMP", "."))  # not used; only for typing
        self.pool = LSPClientPool(workspace=Path("."))

    def tearDown(self):
        self.pool.shutdown()

    def test_get_returns_none_for_unknown_extension(self):
        self.assertIsNone(self.pool.get("/tmp/foo.unknown"))

    def test_register_records_config(self):
        self.pool.register("python", LSPConfig(command=["pylsp"]))
        self.assertIn("python", self.pool._custom_configs)


class TestLSPURIConversion(unittest.TestCase):
    def test_to_uri_absolute(self):
        cfg = LSPConfig(command=["x"])
        client = LSPClient(cfg, workspace=Path("."), server_id="t")
        uri = client._to_uri("C:/Users/test/file.py")
        self.assertTrue(uri.startswith("file:///"))
        self.assertIn("file.py", uri)

    def test_guess_language_id(self):
        cfg = LSPConfig(command=["x"])
        client = LSPClient(cfg, workspace=Path("."), server_id="t")
        self.assertEqual(client._guess_language_id("foo.py"), "python")
        self.assertEqual(client._guess_language_id("foo.ts"), "typescript")
        self.assertEqual(client._guess_language_id("foo.rs"), "rust")
        self.assertEqual(client._guess_language_id("foo.go"), "go")
        self.assertEqual(client._guess_language_id("foo.txt"), "plaintext")


class TestLSPClientIntegrationSubprocess(unittest.TestCase):
    """End-to-end test that actually spawns a real subprocess.

    Skipped by default; set ``nexus_run_subprocess_tests=1`` to enable.
    """

    def setUp(self):
        if not _RUN_SUBPROC:
            self.skipTest("set nexus_run_subprocess_tests=1 to enable subprocess tests")

    def test_round_trip_with_fake_server(self):
        import subprocess
        import sys
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        workspace = Path(tmp.name)
        server = workspace / "fake_lsp.py"
        server.write_text(
            "import json, sys, time\n"
            "REPLIES = [{\"result\": {\"capabilities\": {\"hoverProvider\": True}}}]\n"
            "def read_msg():\n"
            "    headers = {}\n"
            "    while True:\n"
            "        line = sys.stdin.readline()\n"
            "        if not line:\n"
            "            return None\n"
            "        line = line.rstrip('\\r\\n')\n"
            "        if not line:\n"
            "            break\n"
            "        if ':' in line:\n"
            "            k, _, v = line.partition(':')\n"
            "            headers[k.strip().lower()] = v.strip()\n"
            "    length = int(headers.get('content-length', 0))\n"
            "    body = sys.stdin.read(length)\n"
            "    return json.loads(body)\n"
            "def write_msg(msg):\n"
            "    body = json.dumps(msg).encode('utf-8')\n"
            "    sys.stdout.buffer.write(('Content-Length: ' + str(len(body)) + '\\r\\n\\r\\n').encode())\n"
            "    sys.stdout.buffer.write(body)\n"
            "    sys.stdout.buffer.flush()\n"
            "for reply in REPLIES:\n"
            "    msg = read_msg()\n"
            "    if msg is None:\n"
            "        break\n"
            "    if 'id' in msg:\n"
            "        reply['id'] = msg['id']\n"
            "        write_msg(reply)\n"
            "time.sleep(0.5)\n"
        )

        cfg = LSPConfig(command=[sys.executable, str(server)])
        client = LSPClient(cfg, workspace=workspace, server_id="t", request_timeout=3.0)
        client.start()
        try:
            result = client.request("initialize", {"foo": "bar"})
            self.assertIsInstance(result, dict)
            self.assertTrue(result.get("capabilities", {}).get("hoverProvider"))
        finally:
            client.stop()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
