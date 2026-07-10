
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-01-20 - [Fix missing dependency and test runtime failure]
**Learning:** `blessed` was imported but missing from `pyproject.toml` causing test failures. Also, `TestCheckOpenvino` test failed because `sys.modules` patching was testing `jax` instead of `openvino`.
**Action:** When adding imports ensure they are part of `pyproject.toml`. When modifying tests, ensure the patched modules exactly match the target logic.
