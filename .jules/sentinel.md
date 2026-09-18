## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2025-02-28 - Fix SQL Wildcard Injection in LIKE queries
**Vulnerability:** SQL wildcard injection vulnerability found in `src/nexus_agent/tools/rag_search.py`, `src/nexus_agent/memory/long_term.py`, and `src/nexus_agent/memory/episodic.py`. User input was passed to `LIKE` queries with only `%` and `_` characters escaped, but without escaping the escape character `\` itself.
**Learning:** `replace('%', '\\%')` is insufficient for escaping SQL LIKE wildcards because an attacker can pass a single `\` to escape the escape character `\\%`, re-enabling the wildcard `%` injection or breaking the query.
**Prevention:** Always escape the escape character `\` itself before escaping the `LIKE` wildcard characters `%` and `_`. For example: `query.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")`.

## 2025-02-28 - Test dependencies simulation
**Learning:** When simulating missing dependencies in tests using `patch.dict("sys.modules", {"module_name": None})`, it is critical to ensure the mocked module name exactly matches the module being checked. Copy-pasting tests (e.g. from `test_no_jax` to `test_no_openvino`) without updating the mock key (leaving `{"jax": None}`) causes the test to fail.
