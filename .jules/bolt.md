
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-01-24 - [Avoid greedy generator evaluations with glob/rglob]
**Learning:** Evaluating `path.rglob()` or `path.glob()` greedily into a list before slicing or checking for existence takes excessive CPU time and memory on large directories, as every file match is traversed. Using `any(path.glob(...))` for existence checks and `itertools.islice(path.rglob(...), limit)` for limited slices yields ~19x to ~5x speedups respectively by halting the generator early.
**Action:** When validating file existence, prefer `any(path.glob(...))` over `list(path.glob(...)) != []`. When fetching a limited subset of files, prefer `itertools.islice(generator, limit)`.
