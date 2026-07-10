## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-10 - Fix CSWSH vulnerability in WebSocket endpoint
**Vulnerability:** The FastAPI WebSocket endpoint lacked `Origin` header validation, allowing Cross-Site WebSocket Hijacking (CSWSH) attacks.
**Learning:** WebSockets do not have CORS protections by default. The `Origin` header must be explicitly validated against the `Host` header to ensure the request is from a trusted source. `origin == "null"` must also be handled and rejected to prevent bypasses using local HTML files. Extracting the hostname from both headers securely is necessary, especially handling IPv6 addresses and ports.
**Prevention:** Always implement `Origin` header validation in WebSocket endpoints, carefully comparing it against the `Host` header and ensuring `origin == "null"` is not permitted.
