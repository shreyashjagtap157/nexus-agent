## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-10-08 - Fix command injection in Windows Sandbox via cmd.exe
**Vulnerability:** Passing a list of arguments prefixed with `["cmd.exe", "/c"]` to `subprocess.run` on Windows still evaluates shell metacharacters (e.g., `&`, `|`), allowing command injection even if arguments were successfully parsed with `shlex.split`.
**Learning:** While `subprocess.run` with a list is generally safe on Unix to prevent shell expansion, `cmd.exe /c` re-parses the entire command string on Windows, breaking the array-based isolation completely.
**Prevention:** When using `cmd.exe /c` to support Windows built-ins, explicitly reject any parsed arguments containing Windows shell metacharacters before execution.
