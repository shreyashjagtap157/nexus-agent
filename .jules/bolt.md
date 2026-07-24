
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-25 - [Use itertools.islice for lazy evaluation of file traversals]
**Learning:** Evaluating generator outputs into lists greedily (e.g. `[str(f) for f in Path.rglob()][:20]`) forces traversal of the entire directory tree and can use significant memory/time unnecessarily.
**Action:** When only needing a subset of results from an expensive generator, use `itertools.islice(generator, limit)` to lazily consume values and prevent unnecessary work.
