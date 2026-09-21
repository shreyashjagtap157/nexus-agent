
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-21 - [Optimize iter_files custom recursive generator]
**Learning:** Initializing literal structures (like `set({"node_modules", ...})`) inside inner generator loops (like the `for entry in os.scandir:` loop inside `iter_files`) causes excessive memory allocations and significantly degrades iteration performance when dealing with deep folder structures.
**Action:** When optimizing recursive functions, always declare static collections as module-level constants (e.g. `frozenset`). Additionally, pre-compute combined dynamic sets (like merging defaults with `exclude_dirs` arguments) before the first recursion step, and pass the data (or close over it) with an inner `_iter` function to avoid repeated processing overhead.
