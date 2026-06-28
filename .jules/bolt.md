
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-02-19 - [Lazy evaluation of rglob for fast traversal and memory safety]
**Learning:** Using greedy list comprehensions with `rglob` (e.g., `[str(f) for f in path.rglob('*.py')][:20]`) in a large repository forces the evaluation of the entire directory tree, causing severe memory bloat and unnecessary I/O overhead.
**Action:** Always use `itertools.islice(path.rglob('*.py'), limit)` to lazily evaluate generators. This ensures the search stops immediately once the limit is reached, saving significant memory and compute cycles.
