
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-15 - [Refactor os.walk to iter_files to reduce memory bloat]
**Learning:** `os.walk` allocates intermediate lists for directories and files at each step of the directory tree, causing memory bloat and GC pressure on large repositories. Using an `os.scandir` wrapper (like `iter_files`) that yields lazily uses O(1) memory per directory. However, to achieve maximum performance, any custom lookup logic (like skip sets) must be evaluated outside the recursive inner function to avoid repeated allocations.
**Action:** When replacing `os.walk` with `iter_files` or similar generators, always ensure `include_hidden=True` is provided to preserve the default visibility behavior of `os.walk`, and precompute any exclude sets outside the recursive closure.
