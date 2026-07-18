## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-13 - Fix CSWSH in WebSocket endpoints
**Vulnerability:** The `/api/ws/{session_id}` endpoint lacked `Origin` header validation, allowing Cross-Site WebSocket Hijacking (CSWSH) where a malicious website could establish a connection on behalf of an authenticated user.
**Learning:** FastAPI's default `WebSocket` implementation does not enforce same-origin policies. Without explicit validation, WebSockets are vulnerable to cross-origin exploitation just like missing CSRF protection for HTTP requests.
**Prevention:** Always validate the `Origin` header against the `Host` header before accepting WebSocket connections, taking care to extract the hostname correctly (handling ports and IPv6) and explicitly blocking `null` origins to prevent local file bypasses. Programmatic clients typically omit the `Origin` header, so allowing its absence is acceptable.
