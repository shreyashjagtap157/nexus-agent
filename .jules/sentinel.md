## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2026-09-25 - Fix command injection in Sandbox (Windows)
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) was wrapping arguments with `["cmd.exe", "/c"]`, allowing command injection if arguments contain shell metacharacters.
**Learning:** Passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]`, does not bypass shell interpretation.
**Prevention:** To execute safely, pass the target executable and arguments directly to `subprocess.run` without wrapping them in `cmd.exe`.
