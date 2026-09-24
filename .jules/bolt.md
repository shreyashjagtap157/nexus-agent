
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-09-24 - [Optimize fs.iter_files to prevent redundant Path and set allocations]
**Learning:** In custom recursive `os.scandir` loops, instantiating `pathlib.Path` objects at every recursive frame and defining local lookup sets (e.g. `skip_dirs = {"node_modules", ...}`) inside the loop causes significant memory allocation overhead. This can make a custom generator slower than standard `os.walk`.
**Action:** When writing or optimizing recursive directory traversal loops, define skip-sets as module-level `frozenset` constants. Pass raw path strings through the recursion, yielding them to a top-level wrapper that performs the final conversion to `pathlib.Path` objects.
