
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-25 - [Lazy Generator Consumption over Greedy List Comprehensions]
**Learning:** Greedily evaluating a generator into an in-memory list (e.g., `[f for f in generator][:20]`) destroys the performance benefits of generators, causing O(N) memory and time overhead for large data sources like `pathlib.rglob`.
**Action:** When extracting a subset of items from a generator, always use lazy consumption methods like `itertools.islice(generator, limit)` instead of slicing a fully constructed list.
