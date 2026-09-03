
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-05-24 - Optimizing Recursive Traversals
**Learning:** When optimizing custom recursive directory traversals (like wrapping `os.scandir`), initializing exclusion sets inside the function causes unnecessary memory allocation on every recursion.
**Action:** Always pre-compute and define default lookup collections (like skip sets) outside the inner recursive function body, or initialize them globally/once, to prevent massive memory overhead during deep traversals.
