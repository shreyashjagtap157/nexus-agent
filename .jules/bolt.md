
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-25 - [Use lazy evaluation (itertools.islice) instead of loading generator to memory]
**Learning:** Greedily evaluating a generator into a list before slicing (e.g., `[f for f in path.rglob(...)][:20]`) can cause unnecessary memory overhead and file system traversal. Lazy evaluation techniques should be used instead.
**Action:** When limiting items from generator-based operations, use lazy consumption like `itertools.islice(generator, limit)` to prevent full traversal and needlessly loading all items into memory.
