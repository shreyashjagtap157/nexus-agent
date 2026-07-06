## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-24 - Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint in `src/nexus_agent/gui/server.py` did not validate the `Origin` header, allowing malicious websites to connect to the local server if the user is running the GUI.
**Learning:** WebSockets do not respect the Same-Origin Policy (SOP) by default. When running local servers on `0.0.0.0` or `127.0.0.1`, `Origin` header validation against the `Host` header (accounting for IPv6 and port numbers) is critical to prevent CSWSH while maintaining support for legitimate programmatic access (missing Origin).
**Prevention:** Always validate the `Origin` header in WebSocket endpoints, ensuring proper parsing of hostnames and explicit rejection of `null` origins.
