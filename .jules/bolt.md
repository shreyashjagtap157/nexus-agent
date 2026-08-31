## 2026-08-31 - [Iter_Files Utility Regression]
**Learning:** [Replacing `os.walk` (which utilized in-place pruning via `dirs[:] = `) with a generic `iter_files` generator and applying post-traversal file-level filtering causes massive performance regressions, as it forces the program to scan all files inside ignored directories like `.venv` or `node_modules`.]
**Action:** [When refactoring directory traversal, ensure the underlying utility natively supports skipping excluded directories during traversal via an `exclude_dirs` argument, rather than filtering files after the fact.]

## 2026-08-31 - [Test Dependency Mocking]
**Learning:** [When mocking dependencies like `openvino` in tests, explicitly mocking the exact module name (`openvino` instead of a generic or duplicated key like `jax`) is required to ensure tests correctly simulate the missing dependency without side effects.]
**Action:** [Verify the exact dictionary key names when using `patch.dict("sys.modules", ...)` to ensure the correct mock is being applied.]
