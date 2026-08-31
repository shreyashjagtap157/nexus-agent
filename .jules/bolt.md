
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-08-31 - [Optimize File Traversal]
**Learning:** Custom implementations of `os.walk` with manual exclusion lists spread throughout the codebase are slow and brittle. A centralized `os.scandir`-based utility (`iter_files`) performs much better, especially by pruning skipped directories at iteration time, avoiding loading large file trees into memory.
**Action:** Always refactor custom `os.walk` traversals to use the centralized `iter_files` utility in `nexus_agent.utils.fs` for performance consistency, and ensure we propagate exclusions carefully.
