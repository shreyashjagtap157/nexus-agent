## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2026-09-19 - Command injection vulnerability via cmd.exe /c
**Vulnerability:** Passing an array of arguments to `subprocess.run` starting with `["cmd.exe", "/c"]` on Windows allows for command injection because `cmd.exe` interprets shell metacharacters (e.g., `&`, `|`, `>`) within the arguments.
**Learning:** Using `cmd.exe /c` with an array of arguments does not bypass shell interpretation, contrary to the belief that arrays are intrinsically safe from injection in Python's `subprocess`.
**Prevention:** On Windows, to avoid command injection, do not wrap command execution in `cmd.exe /c` when handling parsed user arguments. Instead, execute the target process directly via `subprocess.run(parsed_args)`.
