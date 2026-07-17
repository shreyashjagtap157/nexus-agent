## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix CSWSH in GUI WebSocket
**Vulnerability:** The FastAPI WebSocket endpoint in `src/nexus_agent/gui/server.py` accepted all connections unconditionally, making it vulnerable to Cross-Site WebSocket Hijacking (CSWSH) if a user's browser was tricked into connecting from a malicious origin.
**Learning:** WebSockets do not automatically enforce Same-Origin Policy or CORS policies by default in many frameworks, including standard FastAPI `websocket.accept()`.
**Prevention:** Explicitly parse and validate the `Origin` header against the `Host` header before accepting WebSocket connections, ensuring to handle specific cases like `null` origins and explicitly rejecting unauthorized requests.
