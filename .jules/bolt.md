
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-21 - [Optimize file system traversal across code scanning tools]
**Learning:** `os.walk` in Python materializes a list of all directories and files for each traversed directory layer, which can cause significant memory and CPU overhead when traversing large file trees in multiple tools (like RAG search and Code Intel). Replacing it with an `os.scandir` based generator function that yields items lazily avoids this overhead.
**Action:** When performing deep directory traversal, avoid `os.walk` and instead use the centralized `iter_files(workspace)` utility from `nexus_agent.utils.fs`, augmenting it with `exclude_dirs` or `include_hidden` arguments if needed to preserve precise traversal behaviors safely.
