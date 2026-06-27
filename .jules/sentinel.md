## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-25 - [Add Origin Validation for WebSockets]
**Vulnerability:** Cross-Site WebSocket Hijacking (CSWSH) could allow a malicious website to connect to the local WebSocket server on the user's behalf.
**Learning:** WebSocket endpoints in FastAPI do not automatically validate the Origin header. Local development servers are often vulnerable to CSWSH.
**Prevention:** Always validate the `Origin` header against the `Host` header for WebSocket endpoints, especially in local environments.
