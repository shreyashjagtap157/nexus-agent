
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-01 - [Avoid evaluating full glob iterators in existence checks]
**Learning:** Checking for file existence by evaluating a full `glob` iterator to a list using `list(path.glob(...))` is highly inefficient because it fully materializes all matches in memory before the existence check occurs, which scales poorly in large directories.
**Action:** When only checking if any files match a glob pattern (or needing a partial list), use `any(path.glob(...))` or `itertools.islice(path.glob(...), n)` instead of wrapping the generator in a `list()`.
