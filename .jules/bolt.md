
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - Greedy Evaluation Defeating Generator Optimizations
**Learning:** Optimizing a recursive search (like `Path.rglob`) by using `os.scandir` in a generator function is useless if the caller greedily evaluates the entire generator into a list in memory (e.g., `[str(f) for f in generator][:20]`). This evaluates the entire workspace before slicing.
**Action:** When replacing operations that yield iterators, ensure the consumption is lazy. Use `itertools.islice(generator, limit)` instead of list comprehensions when only a subset of results is needed to realize actual performance gains.
