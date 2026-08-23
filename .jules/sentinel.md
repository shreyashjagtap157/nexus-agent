## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The WebSocket endpoint `/api/ws/{session_id}` in `src/nexus_agent/gui/server.py` did not validate the `Origin` header. Although `CORSMiddleware` was applied to the FastAPI app, it only protects standard HTTP endpoints, not WebSockets, leaving the agent vulnerable to CSWSH where malicious sites could connect and stream data.
**Learning:** FastAPI's `CORSMiddleware` does not inherently protect WebSocket routes. Origin validation for WebSockets must be explicitly implemented within the WebSocket handler before calling `websocket.accept()`.
**Prevention:** Always manually validate the `origin` header from `websocket.headers` against an allowlist before accepting any WebSocket connection.
