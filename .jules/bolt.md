
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-15 - [Optimize os.scandir by avoiding intermediate object creation]
**Learning:** Even when using `os.scandir`, creating `Path` objects or re-allocating lookup sets in hot recursive loops creates measurable GC and instantiation overhead.
**Action:** When writing recursive file system traversal loops, pass paths as raw strings through the recursive calls instead of `Path` objects, and declare static lookup sets as global `frozenset` constants outside the function. Convert to `Path` only when yielding the final results.
