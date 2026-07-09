## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-07-09 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` in `src/nexus_agent/gui/server.py` lacked `Origin` header validation, allowing malicious sites to connect to the local server via WebSocket and issue commands or read data.
**Learning:** When validating `Origin` vs `Host` headers in Python, you must handle IPv6 addresses correctly in the `Host` header (extracting the IP between `[` and `]`) before falling back to string splitting. Additionally, `origin == "null"` must be explicitly rejected to prevent local file data URI bypasses.
**Prevention:** Always validate `Origin` against the request `Host` in WebSocket endpoints, handle missing `Origin` headers to support programmatic clients, and explicitly reject `null` origins.
