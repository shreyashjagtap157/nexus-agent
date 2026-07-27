## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix CSWSH in WebSocket Endpoint
**Vulnerability:** The FastAPI WebSocket endpoint lacked Origin header validation, exposing it to Cross-Site WebSocket Hijacking (CSWSH) attacks.
**Learning:** WebSocket connections initiated from web browsers inherit the authentication context (like cookies) but are not restricted by the Same-Origin Policy. Without explicit Origin validation, a malicious site can hijack the WebSocket session.
**Prevention:** Always validate the `Origin` header against the expected `Host` or a whitelist before accepting WebSocket connections. Use secure parsing for comparisons.
