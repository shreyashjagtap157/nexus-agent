## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-05-24 - Windows Command Injection via cmd.exe
**Vulnerability:** Wrapping parsed shell arguments in `["cmd.exe", "/c"]` exposed the application to command injection because Windows `cmd.exe` evaluates shell metacharacters inside the arguments.
**Learning:** Using `cmd.exe /c` defeats the purpose of parsing arguments into a list when running subprocesses, as it reintroduces shell evaluation.
**Prevention:** Pass parsed arguments directly to `subprocess.run` on Windows without wrapping them in a shell.

## 2025-05-24 - SQLite LIKE Wildcard Escape Bypass
**Vulnerability:** When escaping `%` and `_` for SQLite `LIKE` queries, the backslash `\` escape character itself was not escaped.
**Learning:** Failing to escape the escape character allows attackers to supply inputs like `\%` to bypass wildcard escaping, potentially causing denial of service or logic flaws.
**Prevention:** Always escape the escape character (e.g., `\` -> `\\`) before escaping the actual wildcards.
