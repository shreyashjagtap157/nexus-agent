## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-02-23 - Prevent Windows Command Injection via cmd.exe
**Vulnerability:** When executing commands on Windows, passing `["cmd.exe", "/c"] + parsed_args` to `subprocess.run` exposed the application to command injection via shell metacharacters (e.g., `&`, `|`, `<`).
**Learning:** `subprocess.run` on Windows with `cmd.exe` does not inherently provide array-based argument separation safety, allowing injected metacharacters to alter command execution.
**Prevention:** Explicitly reject parsed arguments containing Windows shell metacharacters before execution when using `cmd.exe /c`.
