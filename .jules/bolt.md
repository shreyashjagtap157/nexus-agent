## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-01-20 - [Avoid reinstantiating sets and `Path` objects in recursive traversals]
**Learning:** Instantiating `set` literals and `Path` objects inside recursive `os.scandir` loops generates substantial overhead. Converting internal traversals to raw strings and declaring static exclusion lists as global `frozenset` variables yields a ~10-15% performance improvement in dense directory tree traversals.
**Action:** Extract loop-invariant static sets into global `frozenset` constants. Pass raw strings (`str`) recursively in system calls, casting to `Path` objects only at the final yield boundary.
