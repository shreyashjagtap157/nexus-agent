
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-16 - [Optimize recursive directory traversals with string paths and global sets]
**Learning:** Initializing default lookup collections inside a recursive function body causes unnecessary memory reallocation overhead on every call. Passing `pathlib.Path` objects through recursive calls also introduces object instantiation overhead.
**Action:** When optimizing recursive functions, define default lookup collections (like skip sets) as global constants (e.g., `frozenset`). Pass paths as raw strings through recursive loops, converting to `pathlib.Path` only when yielding final results.
