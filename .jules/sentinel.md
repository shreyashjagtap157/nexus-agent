## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-28 - CSWSH Protection for FastAPI WebSockets
**Vulnerability:** The FastAPI WebSocket endpoint lacked Cross-Site WebSocket Hijacking (CSWSH) protection, meaning it did not validate if the `Origin` header matched the `Host` header, exposing local agent GUI to unauthorized requests from malicious websites.
**Learning:** Strictly requiring the `Origin` header to match `Host` blocks valid programmatic non-browser clients (like CLI tools or test scripts) that do not send an `Origin` header by default. The validation logic must first check if the `Origin` header is present.
**Prevention:** For local servers, ensure CSWSH protection gracefully handles absent `Origin` headers for programmatic access, while strictly validating `Origin` against `Host` if the header is provided (e.g., by browsers). Ensure validation correctly handles IPv6 hostnames as well.
