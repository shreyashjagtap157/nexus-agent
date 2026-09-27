
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-27 - [Optimize recursive os.scandir by pre-computing skip sets and using raw string paths]
**Learning:** When optimizing recursive file system traversals, defining default lookup collections (like skip sets) inside the function body causes unnecessary memory reallocation overhead on every recursive call. Additionally, passing paths as raw strings through recursive calls and converting to `pathlib.Path` only when yielding final results eliminates instantiation overhead, doubling performance for deep directories.
**Action:** When writing recursive custom directory traversals with `os.scandir`, define exclusion lists or skip sets outside the inner recursive loop as global constants (e.g., `frozenset`), and pass raw strings during recursion instead of objects.
