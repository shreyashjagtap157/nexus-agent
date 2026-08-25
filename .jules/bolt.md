
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Replace slow os.walk with iter_files for directory traversals]
**Learning:** `os.walk` with custom exclude dir lists is slow and less efficient compared to the centralized `iter_files` which leverages an optimized `os.scandir` implementation.
**Action:** Always prefer using the `iter_files` utility from `nexus_agent.utils.fs` over `os.walk` or `pathlib.rglob` for efficient directory traversal in the codebase.

## 2024-06-17 - [Proper module mocking in sys.modules]
**Learning:** When mocking a missing optional dependency (like `openvino`) in a test, using `patch.dict('sys.modules', {'jax': None})` while actually testing `openvino` logic will falsely allow tests to pass locally if the target dependency isn't installed anyway, but will fail in CI environments where the dependency might be present or where proper isolation is needed. The CI failed with an `AssertionError: 1 != 0` in `test_no_openvino` because it was still discovering `openvino`.
**Action:** When testing behavior for missing optional dependencies (e.g., `test_no_openvino`), ensure the *exact* target module in `sys.modules` is mocked to `None` (e.g., `patch.dict('sys.modules', {'openvino': None})`).
