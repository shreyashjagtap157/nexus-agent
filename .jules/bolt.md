
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-11-07 - [Replace pathlib.rglob with stack-based os.scandir for artifact traversal]
**Learning:** Using pathlib.rglob on deeply nested directories causes recursion limit and EMFILE errors, and has overhead from creating intermediate Path objects. A non-recursive, stack-based os.scandir implementation is faster and safer.
**Action:** Always use a stack-based os.scandir approach for unbounded directory traversals when resolving artifacts.
