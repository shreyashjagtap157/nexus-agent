## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-19 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI Server
**Vulnerability:** The FastAPI WebSocket endpoint accepted connections without verifying the `Origin` header against the `Host` header. This allows malicious external websites to establish hijacked WebSocket sessions if the user is running the GUI server locally.
**Learning:** WebSocket endpoints in FastAPI require manual explicit origin validation before calling `accept()` to ensure only authorized frontend applications (or valid local API clients) can connect. Relying on default behavior exposes local services.
**Prevention:** Always validate `urllib.parse.urlparse(origin).hostname` matches the parsed hostname from the `Host` header (accounting for IPv6 and port format) before accepting the WebSocket connection.
