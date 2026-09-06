
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - [Optimize slow os.walk traversals with fast lazy iter_files generator]
**Learning:** Using `os.walk` in heavily repeated file scanning paths (like `SecretScanner`, `CallGraphTool`, and `RepositoryRAGTool`) causes excessive memory overhead by eagerly materializing directory and file lists at every level. Refactoring to use a centralized lazy `iter_files` generator backed by `os.scandir`—with module-level `frozenset` ignore lists—significantly cuts down on memory allocation and recursive loop overhead.
**Action:** When writing directory traversal logic, do not use `os.walk`. Always use the centralized lazy `iter_files` utility from `nexus_agent.utils.fs` and pass necessary `exclude_dirs` directly to the generator.
