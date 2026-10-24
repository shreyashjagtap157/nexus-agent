
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-24 - [Avoid sorting Path objects by string representation]
**Learning:** While sorting `pathlib.Path` objects by their string representation (e.g., `str(item[0])`) is a fast C-level micro-optimization, it introduces functional regressions by breaking hierarchical directory grouping (because lexicographical string sorting interleaves files, e.g., `/` comes after `.`).
**Action:** If downstream logic relies on deterministic tree-like grouping, you must sort using the `Path` object itself to preserve correct hierarchical ordering.
