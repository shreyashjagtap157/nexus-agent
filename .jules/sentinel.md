## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix SQLite wildcard injection in LIKE clauses
**Vulnerability:** User queries utilized SQLite `LIKE` with an explicit `ESCAPE '\\'` clause but failed to escape the backslash itself before escaping `%` and `_`. This allowed trailing backslashes to invalidate the SQL query or bypass escaping, acting as a wildcard injection vulnerability.
**Learning:** When escaping wildcards for SQL `LIKE` clauses using a custom escape character, the escape character itself must always be escaped first.
**Prevention:** Always use a consistent multi-character replacement (e.g., `replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")`) when sanitizing user input for `LIKE` clauses.
## 2024-05-15 - Properly mock missing dependencies with __import__
**Vulnerability:** N/A (Test fragility/CI failure)
**Learning:** In Python 3.10+, mocking `sys.modules` with `None` is often insufficient to reliably simulate a missing optional dependency (like `openvino` or `jax`) during unit tests, leading to flaky CI failures.
**Prevention:** Use `with patch('builtins.__import__', side_effect=ImportError):` to explicitly force an `ImportError` when testing fallback logic for missing dependencies.
