## 2024-05-18 - SQL Injection mitigation logic bug for LIKE ESCAPE
**Vulnerability:** SQL injection logic bug in SQLite parameterized `LIKE` queries with `ESCAPE '\'`
**Learning:** When escaping `%` and `_` for SQLite `LIKE` clauses, failing to first escape the backslash `\` itself allows attackers to pass a trailing `\` (e.g. `\%`), which then escapes the programmatically added escape character, turning the wildcard back into a real wildcard and bypassing intended literal matches.
**Prevention:** Always escape the escape character itself first. For example, `query.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")`.

## 2024-05-18 - Windows Command Injection via cmd.exe wrapper
**Vulnerability:** Command injection on Windows environments in `subprocess.run`
**Learning:** On Windows, using `subprocess.run(["cmd.exe", "/c"] + parsed_args)` does not bypass shell interpretation as intended. Because `cmd.exe` processes the rest of the arguments with shell semantics, shell metacharacters inside `parsed_args` will be interpreted, exposing the application to command injection.
**Prevention:** Pass the target executable and arguments directly to `subprocess.run` as a list on Windows, avoiding wrapping them in `cmd.exe`.
## 2024-05-18 - SQL Injection mitigation logic bug for LIKE ESCAPE
**Vulnerability:** SQL injection logic bug in SQLite parameterized `LIKE` queries with `ESCAPE '\'`
**Learning:** When escaping `%` and `_` for SQLite `LIKE` clauses, failing to first escape the backslash `\` itself allows attackers to pass a trailing `\` (e.g. `\%`), which then escapes the programmatically added escape character, turning the wildcard back into a real wildcard and bypassing intended literal matches.
**Prevention:** Always escape the escape character itself first. For example, `query.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")`.

## 2024-05-18 - Windows Command Injection via cmd.exe wrapper
**Vulnerability:** Command injection on Windows environments in `subprocess.run`
**Learning:** On Windows, using `subprocess.run(["cmd.exe", "/c"] + parsed_args)` does not bypass shell interpretation as intended. Because `cmd.exe` processes the rest of the arguments with shell semantics, shell metacharacters inside `parsed_args` will be interpreted, exposing the application to command injection.
**Prevention:** Pass the target executable and arguments directly to `subprocess.run` as a list on Windows, avoiding wrapping them in `cmd.exe`.
