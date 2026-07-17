## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-17 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` lacked `Origin` header validation, allowing malicious sites to connect via the user's browser, bypassing CORS protections, and controlling the agent (Cross-Site WebSocket Hijacking).
**Learning:** WebSockets do not respect standard CORS policies for connection establishment; the `Origin` header must be explicitly validated during the handshake phase to prevent unauthorized cross-origin connections. `Origin: null` must also be explicitly blocked.
**Prevention:** Always validate the `Origin` against the expected `Host` (parsing hostname securely using `urllib.parse.urlparse` and removing IPv6/ports) in WebSocket routes. For FastAPI, reject the connection using `await websocket.close(code=1008)` or raising a `WebSocketException` before `await websocket.accept()` if the check fails.
