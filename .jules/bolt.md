
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-10 - [Replace nested os.walk with optimized centralized iter_files using os.scandir]
**Learning:** Using `os.walk` to traverse files recursively while maintaining custom exclude lists is prone to high overhead and causes massive performance regressions if exclusions are re-calculated inside every loop iteration, or worse, if directories are walked into and files are filtered post-traversal. Using a unified `iter_files` function using `os.scandir` with `skip_set` initialized once drastically improves filesystem performance across devops scanners and search tools.
**Action:** When replacing localized `os.walk()` structures, meticulously verify and adapt custom exclusion lists to the unified `iter_files` utility logic natively to preserve speed and avoid memory overhead bugs.
