
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-26 - [Replace pathlib.rglob with os.scandir for faster file traversal]
**Learning:** Using `pathlib.Path.rglob()` for deep file traversals adds significant overhead due to intermediate `Path` object creation. A custom stack-based traversal using `os.scandir()` avoids this overhead and yields much faster directory scanning in hot loops.
**Action:** Avoid `pathlib.rglob()` and prefer `os.scandir(..., follow_symlinks=False)` for performance-critical path traversal and file discovery operations.
