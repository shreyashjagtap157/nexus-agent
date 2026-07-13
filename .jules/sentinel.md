## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-07-13 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI WebSocket endpoint lacked `Origin` vs `Host` header validation, making it vulnerable to Cross-Site WebSocket Hijacking (CSWSH). A malicious site could silently connect to the local agent's WebSocket and execute agent actions or read sensitive logs.
**Learning:** FastAPI's WebSocket implementation doesn't enforce origin checks by default. Also, attackers can bypass simplistic origin checks using `origin: null` (e.g., from an iframe or data URI). `Host` headers can also contain IPv6 addresses or ports, necessitating careful parsing to extract just the hostname.
**Prevention:** Always validate `Origin` against `Host` (or an allowed list of origins) for WebSocket connections. Explicitly reject `origin: null` and robustly parse hostnames (especially considering IPv6) rather than doing simple string matching.
