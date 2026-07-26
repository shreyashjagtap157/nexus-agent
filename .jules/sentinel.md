## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint in `src/nexus_agent/gui/server.py` lacked validation of the `Origin` header against the `Host` header. This allows malicious websites to hijack the WebSocket connection and interact with the local agent on the user's behalf.
**Learning:** WebSocket connections are not protected by standard CORS policies. Without explicit `Origin` validation, they are vulnerable to CSWSH attacks, especially on local services binding to permissive interfaces. Parsing IPV6 headers correctly is critical for full local access support.
**Prevention:** Always explicitly validate the `Origin` header against the `Host` header in WebSocket endpoints, using secure hostname parsing (e.g., `urllib.parse`) to prevent port mismatches and handle IPv6 formats correctly.
