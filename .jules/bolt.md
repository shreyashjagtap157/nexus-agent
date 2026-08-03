
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-03 - [Lazy filesystem traversal optimizations]
**Learning:** Replaced `pathlib.Path.rglob()` with `os.scandir()` iteration directly. `rglob()` materializes generators and instantiates heavy `Path` objects during traversal, reducing performance substantially in large directories (e.g. node_modules) even with slicing limits. Using stack-based `os.scandir()` skips ignored directories directly without `Path` overhead and yields huge speedups.
**Action:** When finding matching files with an upper limit, use explicit stack-based iteration via `os.scandir()` instead of `[str(f) for f in path.rglob(...)][:limit]`.
