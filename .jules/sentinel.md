## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI GUI server's WebSocket endpoint (`/api/ws/{session_id}`) lacked explicit origin validation. CORS middleware only protects HTTP endpoints, leaving WebSockets vulnerable to CSWSH where malicious sites can connect to the local server.
**Learning:** WebSockets do not respect Same-Origin Policy (SOP) or CORS headers automatically. If a WebSocket endpoint performs sensitive actions or accesses protected data, the `Origin` header must be explicitly validated against the expected `Host` during the handshake.
**Prevention:** Always validate the `Origin` header against the `Host` header in WebSocket endpoints, carefully parsing hostnames to account for port numbers and IPv6 addresses, and reject unmatched origins with a WebSocketException (e.g., code 1008).
