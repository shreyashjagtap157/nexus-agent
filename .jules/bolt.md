
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-02-28 - [Lazily evaluate generators like rglob with itertools.islice]
**Learning:** Evaluating a generator (like `pathlib.Path.rglob()`) fully into a list before slicing (e.g., `[str(f) for f in Path.cwd().rglob("*.py")][:20]`) completely defeats the purpose of the generator. It forces Python to synchronously traverse the entire directory tree, performing slow disk I/O and consuming memory, only to discard most of the results.
**Action:** When a limited number of results are needed from a generator, always use lazy consumption via `itertools.islice(generator, limit)` instead of list comprehensions and slicing. This provides massive performance gains on deep directory trees.
