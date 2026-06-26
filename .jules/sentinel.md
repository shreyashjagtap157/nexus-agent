## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - [Missing CSWSH Protection on Agent WebSocket Endpoint]
**Vulnerability:** The main agent WebSocket endpoint (`/api/ws/{session_id}`) did not validate the `Origin` header before accepting the connection, making the application vulnerable to Cross-Site WebSocket Hijacking (CSWSH) if a user visits a malicious site while running the local server.
**Learning:** Due to the local offline nature of the agent, it was implicitly trusted, but a browser could still connect to local ports from other origins.
**Prevention:** Always validate the `Origin` header securely matching the `hostname` (using `urllib.parse.urlparse`) against allowed local origins (`127.0.0.1`, `localhost`, and dynamically configured host) when exposing WebSocket endpoints, even for locally-bound servers.
