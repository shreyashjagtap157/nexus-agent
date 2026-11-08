
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-05-20 - Custom os.scandir optimization
**Learning:** replacing rglob with os.scandir improves performance by avoiding RecursionError for deeply nested directories and reducing intermediate Path object allocations during the recursive walk. Also using a non-recursive stack avoids EMFILE (too many open files).
**Action:** Use iter_all_files rather than iter_files for preserving hidden files when replacing rglob
