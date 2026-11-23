
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-11-08 - Replaced rglob with iter_all_files for team artifacts
**Learning:** Path.rglob('*') on deeply nested directories can result in slow execution and high memory usage, and recursive generator approaches can cause RecursionError or open file descriptor limits (EMFILE). A non-recursive stack with os.scandir is significantly faster for broad trees.
**Action:** Use a non-recursive os.scandir stack implementation for traversing potentially massive or deep artifact directories.
