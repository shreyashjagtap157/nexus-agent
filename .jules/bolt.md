
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-21 - [Prevent OOM during file traversals with lazy evaluation]
**Learning:** When using fast directory traversals (like `fast_rglob` with `os.scandir`), avoid greedily evaluating the entire generator into a list in memory (e.g., `[... for f in fast_rglob(...)]`) before applying limits. This negates the memory benefits of generators and can cause Out-Of-Memory (OOM) errors in large workspaces.
**Action:** Use `itertools.islice(generator, limit)` to lazily consume only the necessary number of items from the generator before evaluating them into a list.
