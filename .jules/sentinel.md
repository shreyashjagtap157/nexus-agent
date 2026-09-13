## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix SQL Wildcard Injection Bypass
**Vulnerability:** The SQLite `LIKE` queries escaped `%` and `_` wildcards but failed to escape the backslash (`\`) escape character itself. This allowed an attacker to input `\%`, resulting in a query of `\\%`, which SQLite interprets as a literal `\` followed by an unescaped wildcard `%`.
**Learning:** When writing custom wildcard escape logic for SQL `LIKE` clauses, replacing only the wildcard characters is insufficient if the escape character is not also escaped. The order of replacement is critical: the escape character must be replaced first.
**Prevention:** Always escape the escape character before escaping wildcards (`query.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")`), or preferably use a well-tested query builder that handles escaping automatically.
