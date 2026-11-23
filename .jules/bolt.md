
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-11-09 - Optimize Artifacts Traversals
**Learning:** pathlib.Path.rglob() creates substantial intermediate Path objects and can hit RecursionError on deeply nested directories. Using a stack-based os.scandir traversal improves directory walk performance significantly.
**Action:** Use os.scandir iteratively for traversals where rglob's overhead is a bottleneck, ensuring you keep original Path sorting if downstream expects deterministic tree-order grouping.
