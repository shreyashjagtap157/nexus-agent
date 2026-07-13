## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-03-08 - Fix Cross-Site WebSocket Hijacking (CSWSH) in GUI server
**Vulnerability:** The FastAPI WebSocket endpoint `/api/ws/{session_id}` accepted connections without validating the `Origin` header against the `Host` header. This allowed malicious sites to hijack the WebSocket connection if they trick a user into visiting their page while the local server is running.
**Learning:** WebSockets do not enforce Same-Origin Policy (SOP) by default. The `Origin` header must be explicitly validated, and special care is needed to securely parse and compare hostnames, handling IPv6 addresses, ports, and "null" origins correctly.
**Prevention:** Always implement explicit `Origin` validation on WebSocket endpoints, allowing programmatic clients (where `Origin` is absent) but strictly rejecting mismatched origins and the "null" origin.
