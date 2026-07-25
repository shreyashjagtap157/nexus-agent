
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-25 - [Use itertools.islice to avoid greedy generator evaluation]
**Learning:** Using `[... for x in generator][:limit]` greedily evaluates the entire generator into memory before slicing, which is extremely slow and memory-intensive for large directories (like with `rglob`).
**Action:** Always use `itertools.islice(generator, limit)` when limiting the results of a generator to ensure it is evaluated lazily.
