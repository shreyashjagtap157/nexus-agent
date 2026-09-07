
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-25 - [Optimize os.walk traversals with iter_files]
**Learning:** Standard `os.walk` with custom list comprehensions to exclude directories (like `dirs[:] = [...]`) is slow and brittle. It allocates unnecessary lists and often leads to redundant re-evaluation of exclusion lists. The centralized `iter_files` utility from `nexus_agent.utils.fs` utilizes `os.scandir` to provide a faster, lazy-evaluated iterator that correctly handles custom skips without intermediate allocations.
**Action:** When scanning large directories for tools like secret scanners or RAG indexing, replace `os.walk` with `iter_files`, passing in original `EXCLUDE_DIRS` to preserve logic while gaining the performance benefit of `os.scandir`.
