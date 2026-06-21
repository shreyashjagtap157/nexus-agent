## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-23 - Prevent Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The local WebSocket server endpoint (`/api/ws/{session_id}`) did not validate the `Origin` header. This allowed any external website visited by the user to silently connect to the local WebSocket server and interact with the agent/read local files via CSWSH.
**Learning:** Local WebSocket servers are uniquely vulnerable to cross-site attacks because modern browsers do not enforce Same-Origin Policy on WebSockets, allowing arbitrary sites to connect to `ws://localhost:PORT` if not explicitly blocked.
**Prevention:** Always validate the `Origin` header for local WebSocket servers, ensuring the hostname strictly matches allowed local origins (e.g., `localhost` or `127.0.0.1`).
