
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-26 - [Avoid EMFILE errors by using stack-based directory traversal]
**Learning:** When writing custom recursive directory traversals with `os.scandir` (e.g., to avoid `pathlib.Path.rglob` overhead), using actual function recursion while holding the `os.scandir()` file descriptor open leads to `EMFILE` (too many open files) errors on deeply nested directories.
**Action:** When implementing custom `os.scandir` directory traversals, always use a non-recursive, stack-based `while` loop rather than true recursion to keep only a single directory file descriptor open at any given time.
