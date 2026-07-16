## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix CSWSH in GUI Server WebSockets
**Vulnerability:** The FastAPI WebSocket endpoint in `src/nexus_agent/gui/server.py` did not validate the `Origin` header against the `Host` header, presenting a Cross-Site WebSocket Hijacking (CSWSH) vulnerability.
**Learning:** WebSockets do not adhere to Same-Origin Policy or CORS policies by default. If `Origin` validation is missing, an attacker can trick a victim into opening a malicious site that establishes a WebSocket connection to the local server, taking full control of the agent.
**Prevention:** Always validate the `Origin` header against the expected host or `Host` header in WebSocket connection handlers to ensure requests are originating from trusted sources.
