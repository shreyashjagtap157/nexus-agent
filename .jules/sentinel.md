## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-20 - Prevent Cross-Site WebSocket Hijacking (CSWSH) in GUI
**Vulnerability:** The FastAPI WebSocket endpoint lacked Origin validation, leaving it vulnerable to CSWSH where a malicious site could connect to the local WebSocket server.
**Learning:** WebSockets do not respect CORS policies automatically. The `Origin` header must be explicitly validated against the `Host` header to ensure the connection originated from the same application.
**Prevention:** Always validate the `Origin` header in WebSocket endpoints, ensuring `null` is rejected and hostname parsing correctly handles IPv6 and ports.
