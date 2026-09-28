## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-24 - Windows Subprocess Command Injection Bypass
**Vulnerability:** Command injection via `cmd.exe /c` wrapper in `subprocess.run` on Windows.
**Learning:** Passing arguments as a list starting with `["cmd.exe", "/c"]` to `subprocess.run` on Windows exposes the application to command injection because Python's `subprocess.list2cmdline` automatically double-quotes arguments containing special characters, neutralizing manual shell metacharacter escapes like `^`.
**Prevention:** Execute external commands safely on Windows by passing the target executable and its arguments directly to `subprocess.run` as a list, without wrapping them in `cmd.exe`.
