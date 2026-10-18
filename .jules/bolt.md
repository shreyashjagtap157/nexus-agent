
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-10-18 - [Replace recursive pathlib traversal with non-recursive stack]
**Learning:** In Python, using `pathlib.Path.rglob()` for directory traversal can create significant memory overhead due to the constant instantiation of intermediate `Path` objects. A custom recursive `os.scandir` implementation is faster, but vulnerable to `RecursionError` on deeply nested directories.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer a non-recursive, stack-based `os.scandir` with explicit `follow_symlinks` flags to maximize performance and prevent stack overflows.
