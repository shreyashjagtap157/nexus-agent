## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-11 - Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI GUI server's WebSocket endpoint (`/api/ws/{session_id}`) did not validate the `Origin` header against the `Host` header. This allowed potential Cross-Site WebSocket Hijacking (CSWSH) if a user visited a malicious site while the local server was running.
**Learning:** WebSockets do not respect the Same-Origin Policy (SOP) by default and bypass standard CORS middleware. Even for a local tool, failure to validate origins on WebSocket endpoints exposes the application to unauthorized local network access and CSRF-like attacks.
**Prevention:** Always explicitly validate the `Origin` header against the `Host` header before calling `await websocket.accept()` on any WebSocket endpoint. Explicitly reject `origin == "null"` to prevent bypassing via data URIs or local HTML files, and securely parse IP formats (like IPv6).
