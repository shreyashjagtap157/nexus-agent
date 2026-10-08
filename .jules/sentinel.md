## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2025-05-24 - Fix Windows cmd.exe command injection in Sandbox
**Vulnerability:** The Sandbox module was vulnerable to command injection on Windows because it passed user input to `cmd.exe /c` without properly filtering Windows shell metacharacters.
**Learning:** Even when command arguments are properly tokenized with `shlex.split`, executing them via `cmd.exe /c` bypasses standard escaping, allowing metacharacters like `&` and `|` to execute arbitrary commands.
**Prevention:** Explicitly reject commands containing Windows shell metacharacters when invoking `cmd.exe /c`, instead of relying solely on `shlex` parsing.
