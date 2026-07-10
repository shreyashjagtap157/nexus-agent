## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-15 - CSWSH Protection Implementation
**Vulnerability:** The WebSocket endpoint `/api/ws/{session_id}` lacked Cross-Site WebSocket Hijacking (CSWSH) protection. It did not validate the `Origin` header against the expected `Host`.
**Learning:** Proper CSWSH protection requires not just parsing the `Origin` and comparing it to `Host`, but securely handling IPv6 addresses inside the `Host` header (`[::1]:8000`), rejecting `"null"` origins, and allowing empty origins for programmatic API clients. Additionally, using `urlparse(origin).netloc` fails for IPv6 origins because `netloc` preserves the brackets, while `.hostname` correctly extracts it.
**Prevention:** Always implement `Origin` vs `Host` validation on WebSocket endpoints in FastAPI using `urllib.parse.urlparse(origin).hostname` and gracefully parsing `[::1]` style headers before comparison.
