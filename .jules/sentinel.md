## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-02-20 - Prevent Windows Command Injection in Sandbox
**Vulnerability:** Windows sandbox execution via `cmd.exe /c` allowed command injection using shell metacharacters in parsed arguments.
**Learning:** Even when splitting arguments, passing them to `cmd.exe` exposes the application to injection since `cmd.exe` parses metacharacters before executing the target.
**Prevention:** Explicitly reject arguments containing Windows shell metacharacters when executing commands using `cmd.exe /c`.
