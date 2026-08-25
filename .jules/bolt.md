
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Replace slow os.walk with iter_files for directory traversals]
**Learning:** `os.walk` with custom exclude dir lists is slow and less efficient compared to the centralized `iter_files` which leverages an optimized `os.scandir` implementation.
**Action:** Always prefer using the `iter_files` utility from `nexus_agent.utils.fs` over `os.walk` or `pathlib.rglob` for efficient directory traversal in the codebase.
