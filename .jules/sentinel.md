## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-23 - [Command Injection via cmd.exe in Python's subprocess]
**Vulnerability:** Passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]` on Windows does not bypass shell interpretation and exposes the application to command injection if the subsequent arguments contain shell metacharacters.
**Learning:** Python's subprocess list handling behaves differently on Windows with cmd.exe; it joins arguments in a way that allows shell metacharacters to be executed by cmd.exe, unlike typical Unix shell-less execution.
**Prevention:** To execute safely and avoid shell injection, pass the target executable and its arguments directly to `subprocess.run` without wrapping them in `cmd.exe /c`.
