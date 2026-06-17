## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Prevent Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The local FastAPI WebSocket endpoint (`/api/ws/{session_id}`) did not validate the `Origin` header. This allowed any arbitrary website visited by the user to connect to the local WebSocket server and execute agent commands or eavesdrop on streams.
**Learning:** Local WebSocket servers are highly susceptible to CSWSH because web browsers do not enforce Same-Origin Policy (SOP) on WebSocket connections by default, unlike standard HTTP/REST requests which are protected by CORS.
**Prevention:** Always validate the `Origin` header during the WebSocket handshake before calling `await websocket.accept()`. If the origin is not allowed (e.g., not `127.0.0.1` or `localhost`), reject the connection immediately with a `status.WS_1008_POLICY_VIOLATION`.
