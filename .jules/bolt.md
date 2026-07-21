
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-21 - [Avoid eager generator evaluation for file traversals]
**Learning:** Evaluating glob generators into lists (e.g., `list(path.glob(...))` or list comprehensions) is an anti-pattern that creates memory spikes and unnecessary CPU overhead when checking existence or slicing results.
**Action:** When evaluating if files exist or slicing results from a generator, avoid greedy list conversion. Use lazy consumption like `itertools.islice(generator, limit)` for slicing, and `any(path.glob(...))` for existence checks.
