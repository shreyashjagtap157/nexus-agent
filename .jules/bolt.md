## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-02-24 - [Avoid full traversal loading with generators]
**Learning:** Returning a generator for recursive directory operations (`fast_rglob`) is useless if it gets completely evaluated into a list via list comprehensions before any slicing or limits are applied (e.g. `[f for f in list][:20]`).
**Action:** Use `itertools.islice()` on generators to actually lazily evaluate them and save memory.
