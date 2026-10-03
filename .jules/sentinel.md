## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-10-03 - Fix command injection in Sandbox via cmd.exe /c wrapper
**Vulnerability:** In `src/nexus_agent/core/sandbox.py`, `subprocess.run` wrapped commands in `["cmd.exe", "/c"]` on Windows, which exposes the system to command injection because `cmd.exe` interprets metacharacters (e.g. `&`, `|`, `<`, `>`).
**Learning:** Passing a list of arguments to `subprocess.run` securely isolates arguments unless they are passed through a shell interpreter like `cmd.exe`.
**Prevention:** Execute the target application directly by removing `["cmd.exe", "/c"]` and letting `subprocess` handle the argument quoting safely without interpretation.
