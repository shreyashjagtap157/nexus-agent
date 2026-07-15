
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-01 - [Avoid eager evaluation of rglob generators]
**Learning:** Greedily evaluating `pathlib.rglob()` into a list before slicing (e.g., `list(path.rglob(...))[:20]`) forces traversal of the entire directory tree, which causes severe memory overhead and performance bottlenecks in large repositories.
**Action:** Always use `itertools.islice()` to lazily consume the generator when only a limited subset of results is needed.
