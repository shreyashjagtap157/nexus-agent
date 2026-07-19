## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-10-24 - Prevent Cross-Site WebSocket Hijacking (CSWSH)
**Vulnerability:** The FastAPI WebSocket endpoint lacked validation of the `Origin` header against the `Host` header, presenting a Cross-Site WebSocket Hijacking (CSWSH) risk.
**Learning:** WebSockets do not respect Same-Origin Policy (SOP) or Cross-Origin Resource Sharing (CORS) configurations set for HTTP endpoints. They require explicit manual validation of the `Origin` header.
**Prevention:** Always extract and securely compare the hostname of the `Origin` header against the `Host` header in WebSocket connection handlers before calling `websocket.accept()`. Handle cases where `Origin` is `null` (e.g. data URIs or local HTML files) or absent (e.g. programmatic non-browser clients).
