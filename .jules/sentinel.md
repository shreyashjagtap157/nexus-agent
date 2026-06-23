## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-06-23 - [CSWSH in FastAPI WebSocket Endpoint]
**Vulnerability:** FastAPI `websocket_endpoint` did not validate `Origin` header before calling `await websocket.accept()`.
**Learning:** Accepting a WebSocket connection without Origin validation exposes the application to Cross-Site WebSocket Hijacking (CSWSH), allowing any website to connect and execute commands.
**Prevention:** Always validate `Origin` via `websocket.headers.get("origin")` and `urllib.parse.urlparse` before `websocket.accept()`, ensuring it matches expected local hostnames like `localhost` or `127.0.0.1`.
