
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-20 - [Replace blocking os.walk with optimized iter_files scandir generator]
**Learning:** `os.walk` eagerly materializes directory lists internally which causes significant memory overhead and blocking behavior when scanning large workspaces (like those containing many node_modules or large hidden `.git` objects). Refactoring deep repository scans to use a unified, lazy `os.scandir` implementation (`iter_files`) drastically reduces peak memory overhead and avoids unintended traversal into ignored directories.
**Action:** When implementing new features that require iterating over files in the workspace (like static analysis, secrets scanning, or RAG indexing), always use `iter_files(workspace, exclude_dirs=..., include_hidden=True)` rather than native `os.walk`.
