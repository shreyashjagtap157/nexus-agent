## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-20 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI WebSocket endpoint in `nexus_agent.gui.server` lacked origin validation. This permitted malicious websites loaded in a user's browser to connect to the local development server's WebSocket, potentially executing actions or reading sensitive agent context.
**Learning:** WebSockets, unlike simple REST calls subject to standard CORS preflight, are vulnerable to Cross-Site WebSocket Hijacking if the server does not explicitly validate the `Origin` header against the expected `Host`.
**Prevention:** Always validate the `Origin` header against the request's `Host` header (accounting for IPv4, IPv6, and domains) during the initial WebSocket handshake before accepting the connection.
