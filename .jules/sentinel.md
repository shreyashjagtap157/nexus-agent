## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-19 - Fix Cross-Site WebSocket Hijacking in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` did not validate the `Origin` header against the `Host` header. This allowed malicious websites to open a WebSocket connection to the local agent server and send commands on behalf of the user (Cross-Site WebSocket Hijacking).
**Learning:** WebSocket endpoints in local applications that are accessible from web browsers must explicitly validate the `Origin` header, as they are not protected by standard CORS policies in the same way REST endpoints are. Attackers can use `Origin: null` from data URIs to bypass naive checks.
**Prevention:** Always validate `Origin` against `Host` using secure URL parsing, explicitly handle `null` origins, and correctly parse IPv6 hosts.
