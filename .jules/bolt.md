## 2026-08-31 - [Iter_Files Utility Regression]
**Learning:** [Replacing `os.walk` (which utilized in-place pruning via `dirs[:] = `) with a generic `iter_files` generator and applying post-traversal file-level filtering causes massive performance regressions, as it forces the program to scan all files inside ignored directories like `.venv` or `node_modules`.]
**Action:** [When refactoring directory traversal, ensure the underlying utility natively supports skipping excluded directories during traversal via an `exclude_dirs` argument, rather than filtering files after the fact.]
