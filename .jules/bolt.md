
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-09-07 - [Replace os.walk with optimized os.scandir wrapper iter_files]
**Learning:** Using os.walk for full repository scans creates significant memory overhead and slowness due to in-memory buffering of entire directories before yielding. The custom iter_files() wrapper uses os.scandir for lazy loading and avoids large list allocations.
**Action:** When performing full repository scans, replace os.walk with the iter_files utility from nexus_agent.utils.fs, passing exclude_dirs appropriately.
