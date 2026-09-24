
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-09-24 - [Extract frozenset allocations from hot loops]
**Learning:** When optimizing recursive functions or loops (like `os.scandir` wrappers), declaring literal sets (e.g., `{"node_modules", ".git"}`) inside the loop body causes Python to re-allocate and populate the set on every single iteration, destroying performance. Additionally, passing `Path` objects through recursive calls creates unnecessary object initialization overhead.
**Action:** Always pre-compute skip sets as global `frozenset` constants outside the function. When wrapping file traversals, keep recursive calls purely string-based and only instantiate `Path` objects when yielding the final results.
