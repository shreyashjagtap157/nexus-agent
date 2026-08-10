
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-15 - [Centralize os.scandir traversal utility]
**Learning:** When replacing pathlib.Path.rglob() with os.scandir to improve performance, putting the implementation inside a tool class method like SearchFilesTool._iter_files violates encapsulation if called from other modules.
**Action:** Always extract shared high-performance traversal logic into a public utility function like nexus_agent.utils.fs.iter_files to prevent tight coupling while achieving speedups.
