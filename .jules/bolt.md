
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-27 - [Avoid pathlib.rglob for Artifact Traversals]
**Learning:** Replacing `pathlib.Path.rglob('*')` with a custom stack-based `os.scandir` implementation significantly avoids `RecursionError` and `EMFILE` for deeply nested directory traversals while preserving correct hidden file output via customized tracking, but sorting `os.scandir` results by `Path` objects instead of strings is crucial to preserving the tree-like directory grouping expected by UI clients.
**Action:** When implementing custom directory traversals for UI/API, use stack-based `os.scandir` for performance, but explicitly ensure that deterministic grouping by `Path` instances is preserved.
