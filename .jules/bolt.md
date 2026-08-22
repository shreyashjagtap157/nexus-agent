
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-22 - [Replace slow os.walk with fast os.scandir wrapper iter_files]
**Learning:** `os.walk` coupled with custom `exclude_dirs` filters can be slow when scanning large codebases since it may still traverse into some directories. A centralized generator using `os.scandir` (like `iter_files`) allows for early exit filtering and is faster and avoids redundant logic.
**Action:** Replace `os.walk()` traversals with `iter_files()` from `nexus_agent.utils.fs` in scanning and searching features like `SecurityScanner`, `ImportGraphTool` and `RepositoryRAGTool` for measurable performance boosts and cleaner code.
