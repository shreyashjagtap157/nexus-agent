
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-25 - [Optimize os.walk to os.scandir using iter_files]
**Learning:** `os.walk` generates full lists of directory contents in memory before yielding. When scanning large repositories (like in `devops.py` or `rag_search.py`), this creates significant memory overhead and slow execution times.
**Action:** Replace `os.walk` loops with the centralized `iter_files` utility (which utilizes `os.scandir`) across the codebase. Pass `exclude_dirs` and `include_hidden=True` to preserve behavioral parity while maximizing performance.
