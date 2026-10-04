
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-10-04 - Mocking Optional Dependencies in CI
**Learning:** `patch.dict("sys.modules", {"module_name": None})` is not always sufficient to simulate a missing optional dependency in an environment where it is globally installed. If the target code under test (e.g. `_check_openvino`) imports the dependency in a way that falls back to `importlib.util.find_spec` (or if it's imported within another cached package), the code may still "find" the dependency despite the `sys.modules` patch.
**Action:** When simulating a missing dependency that is globally installed in CI, also mock `importlib.util.find_spec` using `@patch("importlib.util.find_spec", return_value=None)` in conjunction with `patch.dict("sys.modules", {"module": None})` to ensure the module is completely masked.
