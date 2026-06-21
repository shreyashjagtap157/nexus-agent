## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-06-21 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI WebSocket endpoint for real-time chat streaming did not validate the `Origin` header. This allowed malicious sites to establish a WebSocket connection to the local agent server and send/receive messages on behalf of the user, leading to a Cross-Site WebSocket Hijacking (CSWSH) vulnerability.
**Learning:** FastAPI's `CORSMiddleware` applies strictly to HTTP endpoints and does NOT automatically protect WebSocket routes (`@app.websocket`) from unauthorized cross-origin requests.
**Prevention:** Always explicitly validate the `websocket.headers.get("origin")` against a defined list of allowed origins (e.g., `ALLOWED_ORIGINS`) inside the WebSocket endpoint handler before calling `websocket.accept()`. If unauthorized, close the connection with `websocket.close(code=1008)`.
