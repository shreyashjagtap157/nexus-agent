
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-28 - [Use lazy evaluation for pathlib globs]
**Learning:** Using `list(path.glob(...))` or list comprehensions over `path.rglob(...)` greedily evaluates all matching files before performing boolean checks or slicing, which causes memory overhead and slower execution times on large directories.
**Action:** When only checking existence, use `any(path.glob(...))` instead of `list(path.glob(...)) != []`. When limiting results, use `itertools.islice(path.rglob(...), limit)` instead of evaluating the full list before slicing.
