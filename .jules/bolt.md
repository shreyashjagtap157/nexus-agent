
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-10-05 - [Replace list(glob) with any(glob) for fast existence checks]
**Learning:** Using `list(path.glob(...))` loads the entire matched set into memory, whereas `any(path.glob(...))` short-circuits on the first match, resulting in significant performance gains (from ~90ms down to ~30ms or less) for existence checking without full directory scans.
**Action:** When checking if a directory contains a matching file format, always prefer `any(...)` over `list(...)`.
