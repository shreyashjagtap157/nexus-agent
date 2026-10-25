
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-28 - [Stack-based os.scandir prevents EMFILE errors on nested directories]
**Learning:** Using recursion within a `with os.scandir(...)` block keeps parent directory file descriptors open, which can cause `EMFILE` (too many open files) errors on deeply nested directories.
**Action:** When implementing custom `os.scandir` directory traversals, use a non-recursive, stack-based `while` loop to manage traversal and avoid exceeding the open file limit.
