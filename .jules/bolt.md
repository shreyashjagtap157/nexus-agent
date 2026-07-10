
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-10 - [Optimize generator evaluation using lazy slicing and any()]
**Learning:** Using `list()` or list comprehensions before slicing (e.g., `list(path.glob(...))[:20]`) forces the entire generator to evaluate in memory, defeating the performance benefits of generators. Using `any(path.glob(...))` for existence checks instead of `list(...)` is also much faster.
**Action:** When working with generator objects like `path.glob(...)` or `path.rglob(...)`, use `itertools.islice()` to lazily slice the output, and `any()` to efficiently check for existence without iterating over all matches.
