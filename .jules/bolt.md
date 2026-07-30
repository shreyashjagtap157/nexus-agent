
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Avoid pathlib.rglob OOMs with os.scandir early exits]
**Learning:** Using `pathlib.Path.rglob()` to find files like `*.py` creates significant memory overhead and slowness due to instantiating `Path` objects across the whole directory tree before filtering.
**Action:** Implement lazy traversal using `os.scandir()` with an explicit stack, early exit conditions (e.g. `len(matches) < 20`), and filtering for ignored directories to improve performance and prevent OOM on large repositories.
