
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Lazy evaluation for generator traversals]
**Learning:** Using `list(path.glob(...))` or evaluating list comprehensions before slicing (e.g., `[...][:20]`) forces the entire directory tree to be traversed and loaded into memory, causing a significant performance bottleneck for deep directories.
**Action:** When checking for file existence, use `any(path.glob(...))` to stop at the first match. When slicing results, use `itertools.islice(path.rglob(...), limit)` for lazy consumption.
