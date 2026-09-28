## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix Windows command injection via cmd.exe
**Vulnerability:** Command injection vulnerability existed on Windows because commands were parsed into arguments but then blindly passed to `cmd.exe /c`, which parses shell metacharacters like `&` and `|` even when passed in an argument list.
**Learning:** Passing a list of arguments to `subprocess.run` starting with `["cmd.exe", "/c"]` exposes the application to command injection because Windows automatically double-quotes arguments, but cmd.exe still parses `&` before executing the underlying program.
**Prevention:** Pass the target executable and arguments directly to `subprocess.run` without wrapping them in `cmd.exe`.
