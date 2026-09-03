
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-11-20 - [Optimize recursive iter_files skip sets]
**Learning:** Initializing default `skip_dirs` sets inside a recursive generator function like `iter_files` causes unnecessary memory reallocation and dictionary union overhead on every subdirectory traversal.
**Action:** When optimizing recursive functions (e.g., custom directory traversals), define default lookup collections (like skip sets) as global constants (e.g., `frozenset`) outside the function scope. Calculate any custom unions (e.g., with `exclude_dirs`) once at the root call, and pass the finalized frozenset down to recursive calls to eliminate per-directory overhead.
