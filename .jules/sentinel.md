## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix Cross-Site WebSocket Hijacking (CSWSH) vulnerability
**Vulnerability:** The WebSocket endpoint `/api/ws/{session_id}` did not validate the `Origin` header against the `Host` header. This allowed malicious sites to initiate unauthorized WebSocket connections (CSWSH).
**Learning:** Explicitly checking `Origin` against `Host` is critical for WebSocket endpoints, especially those dealing with local connections or sensitive data, and special care is needed to support programmatic non-browser clients (where `Origin` might be absent).
**Prevention:** Always validate `Origin` != "null" and ensure its hostname matches the `Host` header hostname before `await websocket.accept()`. Use secure parsers like `urllib.parse.urlparse` to extract the hostname.
