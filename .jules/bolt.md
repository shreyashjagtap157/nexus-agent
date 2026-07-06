
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-07-06 - [Avoid greedy evaluation on generators]
**Learning:** Using `[x for x in generator][:limit]` greedily evaluates the entire generator in memory before taking the slice. This completely defeats the performance benefits of generators, especially with expensive operations like `rglob()`.
**Action:** Use `itertools.islice(generator, limit)` for slicing generators without eagerly evaluating them.
