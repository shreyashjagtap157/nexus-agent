
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-02-27 - [Lazy Evaluation of Generator over Pathlib.rglob()]
**Learning:** Evaluating the entire output of `rglob()` into a list via list comprehension just to take the first few elements causes severe memory bloat and performance loss, especially in large codebases.
**Action:** Always consume `pathlib.rglob()` generators lazily using `itertools.islice()` when limiting results to avoid unnecessary file system traversal and memory allocation.
