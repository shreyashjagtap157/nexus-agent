## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-28 - Cross-Site WebSocket Hijacking (CSWSH) in GUI
**Vulnerability:** The local GUI WebSocket endpoint did not validate the `Origin` header. This allowed malicious websites visited by the user to silently connect to the local API on localhost and control the agent.
**Learning:** Local applications binding to localhost endpoints must enforce strict Cross-Origin checks, especially on WebSockets which bypass typical CORS protections in browsers.
**Prevention:** Always validate the `Origin` header against the expected `Host` header on WebSocket endpoints while explicitly rejecting `null` origins and handling the absence of the header for API clients.
