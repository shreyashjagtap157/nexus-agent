
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-11-20 - [Replace nested `os.walk` loops with recursive `os.scandir` in filesystem scans]
**Learning:** `os.walk` does significant internal processing across the filesystem structure and yields intermediate paths. Using our cached native `os.scandir` based generator `iter_files` optimizes overhead, skips costly redundant inner `os.stat` queries by immediately tracking paths directly, and leverages outer-scope frozenset caching.
**Action:** When finding optimization targets where directories are recursively walked with manual array culling (`dirs[:] = [...]`), replace them with our fast, centralized `iter_files` directory scanner helper if available.
