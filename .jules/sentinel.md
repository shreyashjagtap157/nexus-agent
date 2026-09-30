## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-02-20 - Fix Command Injection via cmd.exe Wrapping
**Vulnerability:** The sandbox command execution logic on Windows prefixed the parsed command arguments with `["cmd.exe", "/c"]` before passing them to `subprocess.run`.
**Learning:** Python's `subprocess.list2cmdline` automatically escapes arguments by enclosing them in quotes, but `cmd.exe` strips these quotes and evaluates metacharacters like `&&` or `|` before executing the target program, making manual escaping ineffective against command injection.
**Prevention:** Always pass the target executable and its arguments directly as a list to `subprocess.run`. Never wrap them in `cmd.exe /c` (or use `shell=True`) when executing untrusted or parameterized input on Windows.
