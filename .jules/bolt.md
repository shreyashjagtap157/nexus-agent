
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-10 - [Avoid pathlib.rglob for API artifact retrieval]
**Learning:** Using `pathlib.Path.rglob()` to iterate directory structures for API responses creates large overheads by instantiating many Path objects and triggering redundant stats.
**Action:** Implement recursive `os.scandir` algorithms using entry paths directly when creating file listings, preventing scaling issues on deep directory trees.
