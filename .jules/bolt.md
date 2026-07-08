
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-24 - [Lazy Evaluation of Generator File Traversals]
**Learning:** Evaluating generator functions like `pathlib.rglob()` greedily into a list comprehension before slicing (e.g., `[... for f in p.rglob()][:20]`) forces the application to traverse the entire directory tree. This does massive disk I/O and consumes memory unnecessarily before discarding most of the results.
**Action:** Always consume recursive file traversal generators lazily. Use `itertools.islice(generator, limit)` instead of list slicing to stop traversal as soon as the limit is reached, achieving significant speedups in large workspaces.
