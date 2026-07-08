## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-20 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint (`/api/ws/{session_id}`) did not validate the `Origin` header against the `Host` header, allowing malicious websites to initiate WebSocket connections to the local server on a user's behalf.
**Learning:** WebSockets do not respect the Same-Origin Policy (SOP) by default. Without explicit `Origin` validation, a local server bound to `127.0.0.1` or `0.0.0.0` is vulnerable to CSWSH.
**Prevention:** Always validate the `Origin` header against the `Host` header for WebSocket connections, explicitly handling `null` origins and carefully parsing hostnames to support IPv6 and ports securely. Programmatic clients (no `Origin` header) should be permitted.
