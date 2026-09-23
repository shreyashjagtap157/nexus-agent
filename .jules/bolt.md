
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-01-20 - [Pre-allocate skip sets and avoid Path instantiations in recursive os.scandir loops]
**Learning:** In a custom recursive `os.scandir` implementation, allocating sets (like `skip_dirs`) on every recursive call, and passing `Path` objects recursively (which forces `.path` and `str()` conversion), introduces significant overhead. Moving the skip set to a global `frozenset` and passing raw strings down through an inner helper significantly speeds up directory traversal (by roughly 30%).
**Action:** When writing or optimizing recursive directory traversal routines, always pre-allocate skip collections outside the traversal loop, and iterate using native strings to eliminate object instantiation overhead.
