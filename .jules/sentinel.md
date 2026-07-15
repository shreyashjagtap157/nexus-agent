## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-01-22 - Prevent Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint for the GUI server did not validate the `Origin` header against the `Host` header, exposing it to Cross-Site WebSocket Hijacking (CSWSH) attacks.
**Learning:** WebSocket endpoints in web applications must strictly validate the `Origin` header to prevent malicious sites from establishing unauthorized connections on behalf of the user, as WebSockets do not adhere to CORS policies by default.
**Prevention:** Implement explicit `Origin` vs `Host` validation in all WebSocket endpoints, ensuring local network access is handled securely by parsing the hostname and explicitly checking for `null` origins.
