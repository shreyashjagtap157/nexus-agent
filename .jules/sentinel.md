## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2026-11-01 - Fix Command Injection in GitTool Execute
**Vulnerability:** `GitTool.execute` previously allowed arbitrary arguments for allowed subcommands. By passing git flags like `--upload-pack`, `--ext-cmd`, `core.pager`, or `-c` through the arguments, an attacker could execute arbitrary code when git executed, despite limiting the command itself to safe git subcommands.
**Learning:** Limiting the primary execution binary (`git` in this case) and its primary subcommands is not enough. If the arguments are untrusted, attackers can often pass configuration flags or specific parameters that cause the executable to shell out or run another binary under the hood.
**Prevention:** Strictly validate arguments using an explicit blocklist (or allowlist) for dangerous configurations (`-c`, `--upload-pack`, `core.pager`, etc.) before passing them to the process.
