## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Cross-Site WebSocket Hijacking (CSWSH) in FastAPI
**Vulnerability:** The FastAPI `CORSMiddleware` does not protect WebSocket endpoints (`@app.websocket()`). This allowed any external website to establish a WebSocket connection and hijack the session if the user visited a malicious site while running the NexusAgent GUI locally.
**Learning:** WebSocket connections in FastAPI do not enforce CORS policies automatically via `CORSMiddleware`. They bypass the standard HTTP CORS checks.
**Prevention:** Always manually validate the `Origin` header inside the WebSocket endpoint handler before calling `await websocket.accept()`. Use `urllib.parse.urlparse` to securely extract and check the hostname against allowed origins.
