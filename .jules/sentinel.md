## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-10-03 - Fix command injection in subprocess on Windows
**Vulnerability:** Passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]` on Windows exposes the application to command injection because `cmd.exe` interprets shell metacharacters differently, neutralizing Python's escaping.
**Learning:** Wrapping execution in `cmd.exe` on Windows is unsafe even with pre-parsed arguments. Python's `subprocess` automatically handles quoting for native executables via `CreateProcess` when run directly.
**Prevention:** Always pass the target executable and arguments directly to `subprocess.run` without wrapping them in `cmd.exe`.
