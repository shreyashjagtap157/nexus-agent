
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-11 - [Avoid greedy evaluation of pathlib.rglob with list comprehensions]
**Learning:** Evaluating `pathlib.Path.rglob()` inside a list comprehension before slicing (e.g., `[str(f) for f in path.rglob("*.py")][:20]`) forces the entire directory tree to be traversed and loaded into memory, causing massive slowdowns on large codebases.
**Action:** Use `itertools.islice(generator, limit)` to lazily consume only the required number of items from the generator before evaluating it, maintaining speed and reducing memory footprint.
