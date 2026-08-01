
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-08-01 - Pathlib rglob overhead with large excluded directories
**Learning:** The codebase previously used pathlib.Path.rglob() wrapped in list comprehensions (e.g., [f for f in path.rglob(...)][:20]). This greedily loaded entire directory trees into memory without filtering out massive build/dependency directories like node_modules or .venv, causing severe CLI latency and potential OOMs on large workspaces.
**Action:** Replace rglob() with os.scandir() using an explicit stack-based iteration to lazily yield files, enforce early exit constraints natively, and skip ignored directories.
