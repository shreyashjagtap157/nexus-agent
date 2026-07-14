## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-28 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint for the agent loop did not validate the `Origin` header against the `Host` header. This allowed malicious sites to establish WebSocket connections to the local server if a user visited them.
**Learning:** WebSockets do not respect the Same-Origin Policy (SOP) by default. Without explicit `Origin` validation, they are vulnerable to cross-site hijacking. Also, when checking `Origin` against `Host`, it's critical to parse the hostnames to avoid mismatches due to ports or IPv6 formatting.
**Prevention:** Always validate the `Origin` header against the expected `Host` or a list of allowed origins before accepting a WebSocket connection. Ensure programmatic clients without `Origin` headers are handled gracefully if required, while explicitly rejecting `origin == "null"` (data URIs / local HTML).
