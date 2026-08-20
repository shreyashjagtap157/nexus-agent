
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-20 - [Do not remove directory exclusions when replacing os.walk]
**Learning:** When replacing `os.walk` with an optimized file iterator like `os.scandir` (or wrappers like `iter_files`), removing directory pruning logic (`dirs[:] = [d for d in dirs if d not in exclude_dirs]`) will cause massive performance regressions because the iterator will blindly traverse huge dependency directories like `.git` or `node_modules`.
**Action:** Always ensure the custom file iterator implements the exact same directory exclusion logic internally before completely removing the exclusion variables from the parent calling code. Update the internal utility if necessary.
