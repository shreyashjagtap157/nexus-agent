## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-09-14 - SQL Wildcard Injection in LIKE Fallbacks
**Vulnerability:** Found SQL wildcard injection in SQLite `LIKE` query fallbacks when parsing FTS (Full-Text Search) syntax errors. The code improperly tried to escape `%` and `_` without escaping the escape character `\` first, allowing attackers to input sequences like `\%` or `\p` to bypass constraints and inject wildcards.
**Learning:** The order of `str.replace()` calls is critical when implementing manual SQL escaping. Escaping wildcards before the escape character creates logic bugs where the escape character itself inadvertently neutralizes the mitigation.
**Prevention:** Always escape the designated SQL `ESCAPE` character before escaping the actual wildcards (e.g., `query.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")`).
