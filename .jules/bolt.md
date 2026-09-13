
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-13 - [Optimize os.walk traversals in tools and core modules]
**Learning:** `os.walk` iterates deeply over directories and when combined with explicit lists and loop checks it can be slower and less memory-efficient. A custom `os.scandir` implementation can natively filter directories faster while avoiding list comprehensions inside the hot traversal path.
**Action:** Extend utilities like `iter_files` with `exclude_dirs` and `include_hidden` arguments to natively support the advanced filtering required by different tools, dropping the dependency on `os.walk` entirely.
