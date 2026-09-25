
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-09-25 - [Optimize custom os.scandir wrapper in utils/fs.py]
**Learning:** When optimizing recursive functions for deep directory traversals (like `os.scandir` wrappers), instantiating `Path` objects recursively and dynamically re-allocating skip sets inside the generator creates substantial overhead, sometimes negating the benefits over `rglob()`.
**Action:** Always extract static lookup collections (like `skip_dirs`) into a global `frozenset` outside the function scope, and pass string paths recursively through inner functions, casting to `Path` only at the final `yield` step.
