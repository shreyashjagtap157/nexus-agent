
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-02-18 - [Optimize generator evaluation in file traversals]
**Learning:** Greedily evaluating a generator into a list in memory via list comprehension (e.g. `[str(f) for f in Path.cwd().rglob("*.py")][:20]`) or `list(path.glob(...))` completely defeats the lazy nature of generators, causing extreme memory usage and disk I/O on large directories.
**Action:** Use lazy consumption like `itertools.islice(generator, limit)` for slicing, and use `any(path.glob(...))` for efficient file existence checks instead of `list(path.glob(...)) != []`.
