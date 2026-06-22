## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - [Fix Cross-Site WebSocket Hijacking]
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` lacked `Origin` header validation, exposing the local agent to Cross-Site WebSocket Hijacking (CSWSH) if a user visited a malicious website while the local agent server was running.
**Learning:** Even entirely local, offline-first applications with web servers are vulnerable to cross-site attacks. Web browsers automatically send local credentials/cookies and establish WebSocket connections to `localhost` endpoints if instructed by malicious scripts on unrelated sites.
**Prevention:** Always validate the `Origin` header for WebSocket endpoints, especially in local applications, to ensure the connection request originated from the intended frontend application (e.g., `127.0.0.1` or `localhost`).
