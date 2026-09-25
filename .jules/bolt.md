
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-09-25 - [Extract skip sets and avoid excessive Path instantiation in custom os.scandir wrapper]
**Learning:** When using `os.scandir` for recursive traversals (`iter_files`), doing `skip_dirs = { ... }` inside the recursive loop triggers expensive re-allocations on every single directory visited. Furthermore, parsing paths strictly as strings and only converting to `pathlib.Path` at the very end (instead of repeatedly creating `Path` instances down the recursive stack) reduces runtime by another ~30%.
**Action:** Always pre-compute skip sets as module-level `frozenset` globals for recursive functions. When writing tight filesystem loops, operate on raw string paths (`entry.path`) for intermediate recursion instead of re-instantiating heavy `pathlib.Path` objects at every directory depth.
