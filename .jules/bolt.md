
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-07-17 - [Use lazy evaluation for file traversals to avoid OOM]
**Learning:** Greedily evaluating iterators like `Path.rglob()` or `Path.glob()` into a list via `list()` or list comprehensions before slicing/checking existence can cause significant overhead and memory issues on large codebases. This happens often for simple existence checks or taking a top-N slice.
**Action:** Always use `any(path.glob(...))` for existence checks instead of `list(...) != []`, and use `itertools.islice(path.rglob(...), limit)` for bounded traversal.
