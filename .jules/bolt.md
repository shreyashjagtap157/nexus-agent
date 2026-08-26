
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-08-26 - [Avoid materializing glob generators with list()]
**Learning:** Wrapping `pathlib.Path.glob()` in `list()` to check for file existence forces the materialization of all matching paths in memory. For broad queries like `**/*.py` across a large repository, this is an O(N) operation that blocks execution and spikes memory for no reason.
**Action:** When only checking if a pattern matches *any* file, use lazy evaluation with `next(path.glob(pattern), None) is not None` instead of `list(path.glob(pattern))`.
