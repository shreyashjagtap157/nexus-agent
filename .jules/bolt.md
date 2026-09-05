
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-05 - [Replacing os.walk with optimized iter_files]
**Learning:** Using `os.walk` with custom string-based excludes for directory traversal can be extremely slow in large repos, as it allocates `list` structures and does not leverage the speed of `os.scandir` for pruning traversal trees as deeply as needed.
**Action:** When replacing `os.walk` loops to boost performance, always replace with `iter_files` utility but remember to explicitly pass `include_hidden=True` and provide exact original `exclude_dirs` list to safely mimic standard behavior while reaping massive memory and speed benefits without test regressions.
