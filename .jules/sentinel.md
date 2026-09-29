## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix SQL wildcard injection bypass
**Vulnerability:** SQL wildcard injection in parameterized `LIKE` queries. The application escaped wildcards (`%`, `_`) but did not first escape the escape character itself (`\`). This allowed an attacker to bypass the escaping by inputting a string ending in `\` or containing `\%`.
**Learning:** Even when using parameterized queries and attempting to sanitize input for `LIKE` clauses, failing to properly escape the designated `ESCAPE` character completely neutralizes the sanitization.
**Prevention:** Always escape the escape character itself (e.g., `\\`) before escaping the wildcards to ensure the output is safe for a parameter in a `LIKE` clause with an explicit `ESCAPE`.
