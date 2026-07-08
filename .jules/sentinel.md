## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-08 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` did not validate the `Origin` header against the `Host` header. This allowed any external website to initiate a WebSocket connection to the local NexusAgent server on behalf of the user, leading to Cross-Site WebSocket Hijacking (CSWSH).
**Learning:** Even for local-only servers binding to `localhost` or `0.0.0.0`, WebSockets are vulnerable to cross-origin attacks because browsers do not enforce CORS for WebSocket connections. The `Origin` header must be explicitly validated.
**Prevention:** Always implement explicit validation of the `Origin` header in WebSocket endpoints by securely extracting and comparing the hostname from both the `Origin` and `Host` headers. Also, reject `origin == "null"` to prevent bypasses via local HTML files.
