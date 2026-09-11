
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-05-18 - [Optimize directory traversals with iter_files over os.walk]
**Learning:** `os.walk` scans all files in deeply nested directories and creates temporary lists at every step, which is slow and memory-intensive. `iter_files` using `os.scandir` is much faster as it lazily yields paths. Furthermore, initializing skip sets inside recursive generators causes repeated memory allocations.
**Action:** When needing to scan a workspace, always prefer using the centralized `iter_files` utility with `exclude_dirs` instead of `os.walk`. Ensure default skip lists in recursive utilities are defined globally outside the function body.
