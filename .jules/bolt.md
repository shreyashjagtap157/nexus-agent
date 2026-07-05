
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-05 - [Lazy evaluation of rglob to prevent memory overhead]
**Learning:** Evaluating generator outputs (like `rglob`) into lists before slicing causes high memory usage and latency in large directories.
**Action:** Always use `itertools.islice(generator, limit)` for bounded file system traversal to consume lazily.
