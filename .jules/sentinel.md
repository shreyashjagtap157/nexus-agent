## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-20 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint lacked Origin header validation. Since WebSockets do not automatically respect the Same-Origin Policy (SOP) or CORS configurations, an attacker could establish a cross-site WebSocket connection (CSWSH) to interact with the local agent if the user visits a malicious site.
**Learning:** WebSocket endpoints in FastAPI require manual `Origin` vs `Host` validation to ensure the connection originates from a trusted context.
**Prevention:** Always validate `websocket.headers.get("origin")` against `websocket.headers.get("host")` before accepting the connection, and handle IPv6/IPv4 parsing correctly.
