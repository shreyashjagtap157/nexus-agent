## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-09-23 - Prevent Command Injection on Windows subprocess.run
**Vulnerability:** Command injection vulnerability on Windows due to prepending `["cmd.exe", "/c"]` to arguments passed to `subprocess.run(shell=False)`.
**Learning:** Even when `shell=False` is used, explicitly launching `cmd.exe /c` allows Windows CMD to interpret shell metacharacters in the trailing arguments, bypassing Python's expected argument escaping and permitting command injection.
**Prevention:** Avoid prepending `["cmd.exe", "/c"]` to execute commands on Windows when using parsed argument lists. Pass the target executable and its arguments directly to `subprocess.run()`.
