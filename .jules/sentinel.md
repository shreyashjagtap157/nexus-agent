## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-18 - Fix Windows command injection in sandbox execution
**Vulnerability:** In `src/nexus_agent/core/sandbox.py`, the Windows-specific execution pathprepended `["cmd.exe", "/c"]` to the `parsed_args` array when passing it to `subprocess.run()`. This re-introduced shell interpretation layer by cmd.exe, opening the application to command injection if `parsed_args` contain shell metacharacters like `&`, `|`, or `;`.
**Learning:** Passing arguments to `subprocess.run` as a list starting with `["cmd.exe", "/c"]` does not bypass shell interpretation and exposes the application to command injection if the subsequent arguments contain shell metacharacters. The secure way is to pass the target executable and arguments directly.
**Prevention:** Always execute securely parsed commands directly in `subprocess.run()` without routing them through an intermediary shell like `cmd.exe /c` or `powershell -Command`.
