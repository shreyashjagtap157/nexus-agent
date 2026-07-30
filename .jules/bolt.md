
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Lazily evaluate rglob to avoid generating full path tree]
**Learning:** Using `pathlib.Path.rglob()` in an eager list comprehension like `[str(f) for f in path.rglob(...)][:20]` creates massive overhead because it forces Python to crawl the entire directory tree into memory before slicing it. Similarly, `rglob` generates intermediate `Path` objects which are slow to instantiate.
**Action:** When taking a limited subset from a filesystem generator like `rglob`, always use lazy consumption via `itertools.islice(generator, limit)` instead of list comprehensions. For performance-critical recursive traversals, replace `rglob` entirely with a custom `os.scandir` generator to avoid `Path` object overhead.
