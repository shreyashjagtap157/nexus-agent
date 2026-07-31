
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-31 - [Replace slow pathlib.rglob with fast os.scandir stack for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom iterative `os.scandir` implementation using a stack is much faster for tasks like finding workspace files and creating checkpoints, especially when handling deeply nested folders, as it avoids recursion limits and intermediate Path objects.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer an explicit stack using `os.scandir` with explicit `follow_symlinks` flags and manual filtering of skip directories instead of `pathlib.rglob()`.
