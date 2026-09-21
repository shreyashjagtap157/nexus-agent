## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-09-21 - SQL LIKE Wildcard Injection Bypass
**Vulnerability:** SQL wildcard injection via unescaped backslashes in parameterized LIKE queries.
**Learning:** When mitigating SQL wildcard injection in SQLite by escaping `%` and `_`, the escape character itself (`\`) must also be escaped. Otherwise, an attacker can input a backslash to escape the application's added escape character, causing the wildcard to be interpreted as a wildcard rather than a literal character (e.g. inputting `\` combined with an appended `%` creates `\%` which evaluates to a literal `%`, bypassing intended matching logic).
**Prevention:** Always escape the escape character (e.g., `\\`) before escaping the wildcard characters (`%` and `_`) when constructing LIKE query strings.
