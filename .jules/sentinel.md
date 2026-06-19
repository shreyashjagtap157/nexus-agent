## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-19 - Fix CSWSH in GUI Server WebSockets
**Vulnerability:** The FastAPI WebSocket endpoint for the GUI server (`/api/ws/{session_id}`) accepted connections from any origin, which opened it up to Cross-Site WebSocket Hijacking (CSWSH) if a user visits a malicious website while running the agent locally.
**Learning:** FastAPI's `CORSMiddleware` does not inherently protect WebSockets from Cross-Origin requests. `Origin` headers must be explicitly validated in WebSocket connection handlers to ensure requests are only accepted from allowed domains (e.g. `localhost`). If an attacker could omit the `Host` header, an overly simple check like `if host_header and ...` could be bypassed to fail open.
**Prevention:** Explicitly validate `websocket.headers.get("origin")` against an allowed list of hosts before calling `await websocket.accept()`. Default to failing closed.
