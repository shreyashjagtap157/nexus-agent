
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-10-09 - Avoid list() on glob results for file existence checks
**Learning:** Using `list(path.glob(...))` for file existence checks evaluates the entire directory tree and loads all matching `Path` objects into memory.
**Action:** When checking if any file matches a glob pattern, use a short-circuiting generator expression like `any(True for _ in path.glob(...))` to optimize performance and memory usage.
