## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-10-25 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint (`/api/ws/{session_id}`) accepted connections without validating the `Origin` header. FastAPI's `CORSMiddleware` only protects HTTP routes, leaving WebSockets vulnerable to CSWSH where an attacker-controlled site can establish a connection and interact with the local agent.
**Learning:** WebSockets do not respect Same-Origin Policy (SOP) by default and are not covered by standard HTTP CORS middleware. The `Origin` header must be manually validated against the `Host` header to ensure the request originated from the expected frontend.
**Prevention:** Always validate the `Origin` header in WebSocket endpoints, taking care to compare hostnames securely (ignoring ports to support local network access) and explicitly rejecting `origin == "null"` (which bypasses checks via data URIs/local files) while allowing `None` for non-browser clients.
