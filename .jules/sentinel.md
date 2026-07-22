## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Missing CSWSH protection in WebSocket
**Vulnerability:** The WebSocket endpoint (`/api/ws/{session_id}`) lacked Cross-Site WebSocket Hijacking (CSWSH) protection, failing to validate the `Origin` header against the `Host` header.
**Learning:** Even with CORS configured for REST endpoints, WebSockets require explicit origin validation in the connection handler because browsers do not enforce CORS policies on WebSocket handshakes.
**Prevention:** Always validate the `Origin` header against the `Host` header (extracting the hostname to account for ports) and explicitly handle programmatic clients (no Origin) when establishing WebSocket connections.
