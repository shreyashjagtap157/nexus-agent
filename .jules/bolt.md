
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-25 - [Custom os.scandir generator must yield directories to match rglob]
**Learning:** When replacing `pathlib.Path.rglob('*')` with a custom `os.scandir` generator for performance, simply replacing it with a version that only yields files will break code that expects the generator to also yield directory and symlink paths.
**Action:** Ensure the custom `os.scandir` generator explicitly yields `Path(entry.path)` for all entries *before* checking `entry.is_dir()` and pushing to the recursion stack, to precisely mirror the behavior of `rglob`.
