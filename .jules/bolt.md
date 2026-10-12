
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-15 - [Using sorted() around file iterators buffers everything in memory]
**Learning:** When replacing rglob with a faster os.scandir wrapper (like iter_files), wrapping it in sorted() buffers all Path objects in memory. For optimal memory usage, sorting should be avoided if possible, or applied minimally. However, if preserving Path tuple sorting logic is strictly required to prevent regressions, sorting the Path objects is necessary.
**Action:** Always verify if downstream logic actually depends on deterministic directory sorting before applying sorted() to file iterators to preserve memory.
