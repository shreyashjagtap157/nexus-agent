## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix command injection in Sandbox Windows execution
**Vulnerability:** The `Sandbox.execute` method passed parsed arguments to `subprocess.run` prefixed with `["cmd.exe", "/c"]` on Windows. This exposes the application to command injection because `subprocess.list2cmdline` double-quotes arguments containing shell operators, neutralizing manual escapes and allowing arbitrary command execution.
**Learning:** Wrapping safely parsed arguments inside `cmd.exe /c` on Windows defeats the security of list-based argument passing in `subprocess`, re-introducing shell injection risks.
**Prevention:** To safely execute commands on Windows using `subprocess.run`, pass the target executable and arguments directly as a list without invoking the command shell (`cmd.exe`).
