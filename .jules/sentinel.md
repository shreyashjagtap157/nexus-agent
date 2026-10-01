## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix SQL wildcard injection in LIKE query fallbacks
**Vulnerability:** The SQLite FTS5 fallback logic used parameterized `LIKE` queries with `ESCAPE '\'`, escaping user input using `query.replace('%', '\\%').replace('_', '\\_')`. However, it failed to escape the escape character itself (`\`). This allowed an attacker to bypass the escaping by inputting a trailing backslash or `\%`, which neutralized the mitigation and allowed arbitrary wildcard matching, potentially causing Denial of Service or exposing unintended data.
**Learning:** When implementing manual escaping for SQL `LIKE` wildcards (`%` and `_`), failing to escape the chosen escape character introduces an injection vector that allows the escaping logic to be bypassed entirely.
**Prevention:** Always escape the designated escape character (e.g., replace `\` with `\\`) before escaping the wildcard characters to ensure all characters are treated literally.
