## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-27 - Fix Command Injection in Windows sandbox execution
**Vulnerability:** The sandbox execution layer incorrectly prefixed parsed commands with `["cmd.exe", "/c"]` on Windows, intending to bypass shell interpretation but actually causing `cmd.exe` to interpret shell metacharacters within the arguments, enabling command injection.
**Learning:** Wrapping arguments with `cmd.exe /c` does not isolate them from shell metacharacter evaluation on Windows, unlike executing binaries directly.
**Prevention:** To execute safely on Windows and Unix, pass the target executable and its arguments directly to `subprocess.run` without a shell wrapper like `cmd.exe /c` or `sh -c`.
