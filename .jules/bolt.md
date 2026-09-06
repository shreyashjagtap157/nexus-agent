
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Optimize directory traversals with iter_files and os.scandir]
**Learning:** `os.walk()` can be highly inefficient for directory traversal, especially when it scans large node_modules or .git folders before exclusion filtering can be applied. While `nexus_agent.utils.fs.iter_files` was built to optimize this via lazy `os.scandir`, it initially lacked the ability to accept custom exclusion lists or allow hidden files, preventing it from being adopted in specific tools (like RAG Search and DevOps scanning).
**Action:** When replacing `os.walk` with centralized traversal utilities, make sure to upgrade the utility first to support parameterizing `exclude_dirs` and `include_hidden` flags. This allows replacing synchronous `os.walk` with lazy generators safely across diverse modules without losing custom exclusion filtering. Always define default exclusion sets globally (e.g. `frozenset`) to avoid reallocating memory on recursive generator calls.
