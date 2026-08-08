
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-08-08 - [Lazy file traversal optimization using itertools.islice]
**Learning:** Using list comprehensions with `Path.rglob` (e.g. `[str(f) for f in Path.cwd().rglob("*.py")][:20]`) forces eager evaluation, causing the entire directory tree to be traversed and loaded into memory before slicing, which can lead to severe performance bottlenecks or OOM errors in large workspaces.
**Action:** Always prefer lazy generator patterns (e.g., generator expressions combined with `itertools.islice`) when only a subset of results is needed from recursive file system operations. Reuse optimized internal tools (like `SearchFilesTool._iter_files`) to respect standard exclusion directories (like `.git` and `node_modules`).
