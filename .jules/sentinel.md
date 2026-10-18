## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.
## 2024-05-24 - Fix path traversal bypass in boundary checks
**Vulnerability:** Path boundary checks using `str.startswith()` are vulnerable to partial directory name matches if `os.sep` is not carefully appended or if identical paths are not properly excluded. This allowed a malicious directory matching the workspace name prefix (e.g. `/workspace_malicious`) to bypass containment checks in `Sandbox._resolve_safe_path` and `Orchestrator._cmd_debate`.
**Learning:** `str.startswith()` is fundamentally unsafe for path containment validation.
**Prevention:** Always use `os.path.commonpath([root, path]) == root` to safely verify path containment boundaries.
