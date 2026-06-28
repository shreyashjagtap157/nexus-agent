## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-14 - Fix CSWSH vulnerability in local WebSocket API
**Vulnerability:** The premium dashboard local WebSocket API endpoint (`/api/ws/{session_id}`) lacked an Origin header check. This could allow Cross-Site WebSocket Hijacking (CSWSH), letting a malicious website trick a user's browser into connecting to the local server, sending commands to the LLM agent, and executing arbitrary code on the local machine.
**Learning:** WebSockets do not respect CORS headers. You must explicitly validate the `Origin` header manually, especially on local tools/services that bind to `localhost` or `127.0.0.1` which are naturally exposed to any website the user visits.
**Prevention:** Always implement explicit `Origin` validation logic in any WebSocket endpoints, and handle `origin == "null"` explicitly to block circumvention via data URIs or local HTML files.
