
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-10-24 - [Avoid greedy evaluation of glob generators]
**Learning:** Evaluating `path.rglob()` or `path.glob()` completely into a list using `list(path.glob(...))` or `[x for x in path.rglob(...)]` before slicing or checking existence consumes excessive memory and causes severe performance degradation on large directories.
**Action:** Use `any(path.glob(...))` for existence checks and `itertools.islice()` for slicing generators lazily to avoid loading the entire directory tree into memory.
