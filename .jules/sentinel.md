## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-02-18 - [Fix Cross-Site WebSocket Hijacking (CSWSH)]
**Vulnerability:** The local GUI server accepted WebSocket connections from any Origin, allowing malicious websites to connect to the agent's WebSocket API (`/api/ws/{session_id}`).
**Learning:** For local developer tools exposing WebSockets, the `Origin` header must be validated to prevent CSWSH attacks, since cookies/local credentials might automatically authenticate requests.
**Prevention:** Enforce strict Origin validation checking against `localhost`, `127.0.0.1`, and the server's configured `bind_host`. Reject unexpected Origins with a 1008 policy violation status.
