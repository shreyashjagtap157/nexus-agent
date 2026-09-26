
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-26 - [Optimize skip lists in os.scandir recursions]
**Learning:** When using custom recursive file traversals with `os.scandir`, re-creating `set` lookups (e.g., `skip_dirs = {"node_modules", ...}`) inside the generator yields huge memory and performance overhead per directory entry. Furthermore, continually re-instantiating `pathlib.Path` objects down the recursive call stack compounds this overhead.
**Action:** Always pre-compute skip sets as module-level `frozenset` constants. When making a recursive wrapper to return `Path` objects, use a private inner recursive generator that yields raw strings, and only cast to `Path` objects in the outermost wrapper to avoid deep instantiation costs.
