## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix CSWSH vulnerability in WebSocket endpoint
**Vulnerability:** The FastAPI WebSocket endpoint in `src/nexus_agent/gui/server.py` lacked Cross-Site WebSocket Hijacking (CSWSH) protection, allowing unauthorized cross-origin connections since WebSockets bypass standard CORS policies.
**Learning:** FastAPI's `CORSMiddleware` does not protect WebSockets. Explicit validation of the `Origin` header against the `Host` header is required to prevent cross-origin hijacking.
**Prevention:** Always extract and parse the `Origin` and `Host` headers in WebSocket endpoint handlers, ensuring they match before accepting the connection. Reject connections with `origin == "null"` to prevent bypassing origin checks.
