## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix CSWSH and TestClient bugs in FastAPI WebSockets
**Vulnerability:** The WebSocket endpoint lacked Origin header validation, exposing it to Cross-Site WebSocket Hijacking (CSWSH). Additionally, passing `max_size` to `receive_text()` caused TypeErrors with Starlette's `TestClient`.
**Learning:** Attackers can bypass naive origin checks using `origin == "null"` via data URIs or local files. Also, Starlette's test session doesn't support the `max_size` parameter in `receive_text()`.
**Prevention:** Always validate `Origin` against the `Host` header, explicitly reject `null` origins, and use manual length validation for incoming WebSocket messages when using TestClient.
