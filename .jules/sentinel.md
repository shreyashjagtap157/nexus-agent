## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-10-09 - Windows Command Injection via subprocess.run
**Vulnerability:** Command injection vulnerability on Windows systems when using `subprocess.run` with a list starting with `["cmd.exe", "/c"]` and unvalidated parsed arguments.
**Learning:** Even when passing arguments as a list to `subprocess.run` (which normally avoids shell injection on Unix), prepending `cmd.exe /c` on Windows re-introduces shell evaluation. Any shell metacharacters (e.g. `&`, `|`) present in the arguments will be interpreted by `cmd.exe`.
**Prevention:** Explicitly reject arguments containing Windows shell metacharacters before executing them with `cmd.exe /c`, or avoid using `cmd.exe` entirely if shell built-ins are not strictly needed.
