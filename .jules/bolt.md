
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-31 - Greedy Generator Evaluation in Python File Traversals
**Learning:** List comprehensions like `[f for f in path.rglob(...)][:20]` greedily evaluate the entire generator before slicing, which forces a full traversal of the directory tree and needlessly loads all matches into memory. This is especially problematic for filesystem operations over large directories.
**Action:** Always use `itertools.islice(generator, limit)` for generator-based operations when only a subset of results is needed to ensure lazy consumption and fast early exits.
