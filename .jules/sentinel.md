## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-19 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The WebSocket endpoint (`/api/ws/{session_id}`) in `src/nexus_agent/gui/server.py` did not validate the `Origin` header against the `Host` header. This allowed malicious sites to connect to the local dashboard WebSocket and execute agent commands on behalf of the user.
**Learning:** WebSocket endpoints that do not rely on standard HTTP cookies for authentication are still vulnerable to Cross-Site Hijacking if the origin is not explicitly validated against the expected host.
**Prevention:** Always validate the `Origin` header against the `Host` header in WebSocket endpoints, explicitly rejecting unauthorized origins, including `"null"` which can be used to bypass checks.
