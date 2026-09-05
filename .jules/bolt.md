
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-25 - [Optimize codebase traversals with os.scandir wrapper]
**Learning:** Using `os.walk()` combined with in-place list pruning (`dirs[:] = [...]`) is slow because it eagerly constructs large lists of strings at each directory level and blocks on internal stat calls.
**Action:** Replace `os.walk()` directory traversals with centralized utility wrappers like `iter_files(workspace)` that natively use an optimized `os.scandir` implementation and support conditional exclusions directly during iteration.
