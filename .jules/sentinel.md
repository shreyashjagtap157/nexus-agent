## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-07-16 - Prevent Cross-Site WebSocket Hijacking (CSWSH)
**Vulnerability:** The `/api/ws/{session_id}` WebSocket endpoint lacked `Origin` header validation, allowing malicious websites to hijack a user's WebSocket connection if they visited the attacker's site while running the local server.
**Learning:** By default, FastAPI/Starlette does not strictly enforce Origin matching for WebSockets unless explicitly configured or checked. WebSockets bypass traditional CORS policies.
**Prevention:** Always validate the `Origin` header against the expected `Host` header for WebSocket endpoints to prevent CSWSH attacks. Ensure you parse hostnames accurately and handle cases like IPv6 and `origin == "null"`.
