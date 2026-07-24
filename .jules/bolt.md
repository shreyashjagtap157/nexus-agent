
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-24 - [Replace slow pathlib.rglob with fast os.scandir for file finding]
**Learning:** Using `pathlib.Path.rglob()` in fallback logic (like finding matching files for UI autocompletion or checkpoints) causes unacceptable UI freezes due to overhead in instantiating intermediate `Path` objects on every iteration.
**Action:** Replace all `rglob` occurrences in hot paths with custom recursive generators using `os.scandir(..., follow_symlinks=False)` to maximize traversal performance.
