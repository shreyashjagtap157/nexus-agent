## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix CSWSH (Cross-Site WebSocket Hijacking) in FastAPI server
**Vulnerability:** The FastAPI WebSocket endpoint didn't validate the `Origin` header. An attacker could hijack local models by initiating WebSocket connections from attacker-controlled domains.
**Learning:** Local servers bounding to `0.0.0.0` or `127.0.0.1` are still vulnerable to CSWSH if the Origin is not explicitly checked against the Host header. Furthermore, attackers can bypass strict origin checks by utilizing data URIs or local HTML files which result in `Origin: null`.
**Prevention:** Explicitly validate `Origin` against the `Host` header on all WebSocket routes before `.accept()`. Handle IPv6 cases carefully (e.g., `[::1]:8000`) and explicitly reject `Origin: null`, while still permitting absent origins to support non-browser clients.
