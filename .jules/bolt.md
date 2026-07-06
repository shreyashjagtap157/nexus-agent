
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-21 - [Use itertools.islice for lazy evaluation on rglob generators]
**Learning:** Evaluating a pathlib.rglob() generator greedily using a list comprehension (e.g., `[str(f) for f in rglob(...)][:20]`) forces the entire directory tree to be scanned before truncation, which causes high memory usage and long execution times on large directories.
**Action:** Always wrap generators that need to be truncated in `itertools.islice()` (e.g., `[str(f) for f in itertools.islice(rglob(...), 20)]`) to maintain lazy evaluation and avoid blocking file system traversal on large trees.
