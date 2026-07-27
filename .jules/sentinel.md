## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix CSWSH vulnerability in WebSocket endpoint
**Vulnerability:** The `/api/ws/{session_id}` WebSocket endpoint lacked Origin header validation, allowing Cross-Site WebSocket Hijacking (CSWSH).
**Learning:** WebSocket connections are not protected by standard CORS policies and require explicit validation of the Origin header against the expected Host.
**Prevention:** Always validate the `Origin` header in WebSocket endpoints by comparing its extracted hostname securely against the `Host` header, falling back or rejecting if mismatched.
