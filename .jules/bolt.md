
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-01 - [Optimize recursive directory traversals by pre-computing sets and using raw strings]
**Learning:** When implementing custom recursive directory traversal loops (e.g., wrapping `os.scandir`), creating exclusion lists or skip sets inside the inner recursive loop and instantiating `pathlib.Path` objects at every depth layer creates massive memory and GC overhead. In tests, it added almost 50-80% overhead for deep trees.
**Action:** Always pre-compute exclusion collections as global constants (like `frozenset`) outside the recursive function scope. When writing recursive file system functions, pass paths as raw strings through the recursive calls to eliminate instantiation overhead, converting to `Path` only when yielding final results.
