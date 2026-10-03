## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-10-03 - Fix command injection in subprocess on Windows
**Vulnerability:** Passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]` on Windows exposes the application to command injection because `cmd.exe` interprets shell metacharacters differently.
**Learning:** Preventing command injection on Windows while maintaining the ability to run shell built-ins requires strictly rejecting parsed arguments containing metacharacters (e.g. `&`, `|`, `<`, `>`, `%`, `\n`, `\r`) before invoking `cmd.exe /c`.
**Prevention:** Explicitly deny execution if arguments contain `cmd.exe` metacharacters when wrapping commands in `cmd.exe /c`.
