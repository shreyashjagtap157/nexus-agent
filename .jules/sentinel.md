## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-09 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The local WebSocket endpoint (`/api/ws/{session_id}`) accepted connections without validating the `Origin` header against the `Host` header, exposing the agent to Cross-Site WebSocket Hijacking (CSWSH). A malicious website could connect to the local server and execute arbitrary agent tasks.
**Learning:** Local WebSocket servers are particularly vulnerable to CSWSH because browsers automatically include credentials and allow cross-origin WebSocket connections by default. We must explicitly validate that the origin matches the requested host.
**Prevention:** Always validate the `Origin` header against the `Host` header for all WebSocket endpoints. Explicitly handle edge cases like IPv6 addresses and `null` origins (from data URIs or local files). Non-browser clients without an `Origin` header can be permitted if appropriate.
