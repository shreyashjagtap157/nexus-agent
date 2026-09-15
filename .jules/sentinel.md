## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-02-21 - SQL Wildcard Injection in SQLite LIKE Fallback
**Vulnerability:** SQL wildcard injection due to unescaped backslashes in `LIKE` queries.
**Learning:** When escaping `%` and `_` for SQLite `LIKE` queries using `ESCAPE '\'`, the backslash character itself (`\`) must be escaped *first*. Otherwise, user input like `\%` becomes `\\%`, neutralizing the escape character and executing as a wildcard.
**Prevention:** Always use `.replace("\\", r"\\")` before escaping wildcard characters in SQL strings.
