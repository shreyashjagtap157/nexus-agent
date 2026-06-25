
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - [Optimize file discovery with os.scandir]
**Learning:** `pathlib.Path.rglob()` is slow and memory-intensive for large directories because it eagerly yields intermediate `Path` objects and searches recursively before slicing (when combined with list comprehensions). Using a custom recursive `os.scandir` implementation with `fnmatch` (and lazy evaluation via `itertools.islice`) significantly speeds up operations like workspace scanning or check-pointing by limiting file I/O strictly to the items requested.
**Action:** When finding a limited number of files recursively, always prefer a custom `os.scandir` generator and lazy consumption (like `islice`) over `list(path.rglob)[:limit]`.
