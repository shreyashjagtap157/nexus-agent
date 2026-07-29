
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-29 - Optimize file traversal by replacing Path.rglob with os.scandir
**Learning:** `pathlib.Path.rglob()` creates significant overhead by generating intermediate `Path` objects and greedily finding matches.
**Action:** Use a custom recursive generator with `os.scandir()` and `itertools.islice()` for faster, lazy file traversal.
