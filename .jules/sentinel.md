## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-18 - Fix command injection in Sandbox execute for Windows
**Vulnerability:** The command isolation sandbox `Sandbox.execute` executed commands on Windows using `cmd.exe /c` combined with arguments passed as a list to `subprocess.run()`.
**Learning:** On Windows, passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]` exposes the application to command injection because Python's automatic escaping in `list2cmdline` is not safe when evaluated by the `cmd.exe` shell.
**Prevention:** To execute safely, pass the target executable and parsed arguments directly to `subprocess.run` without wrapping them in a shell like `cmd.exe`.
