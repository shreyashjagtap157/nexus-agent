
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-11-20 - [Replace os.walk with iter_files for faster directory traversal]
**Learning:** Using `os.walk()` with custom `exclude_dirs` lists for directory traversals can be slow and brittle compared to a centralized utility using `os.scandir` with explicit early exit logic for ignored directories.
**Action:** Replace instances of `os.walk` with the `iter_files` utility from `nexus_agent.utils.fs` to optimize file system traversals, reducing memory usage and time taken by avoiding deep traversal of ignored directories like `node_modules` or `.git`.
