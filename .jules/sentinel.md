## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-06-25 - Prevent Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI GUI server (`src/nexus_agent/gui/server.py`) contained a WebSocket endpoint that did not validate the `Origin` header before accepting the connection. This could allow an attacker to hijack a WebSocket connection via a malicious website.
**Learning:** WebSocket connections in FastAPI (and many other frameworks) do not enforce Same-Origin Policy by default. Explicitly checking the `Origin` header against an allowed list is necessary for secure WebSocket endpoints.
**Prevention:** Always validate the `Origin` header in WebSocket endpoints using `urllib.parse.urlparse` to compare the hostname against allowed origins (e.g., `127.0.0.1`, `localhost`, and the configured binding host).
