
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-06-26 - [Optimization using fast_rglob]
**Learning:** `pathlib.Path.rglob()` is slow due to creating intermediate Path objects. Using `os.scandir` is much faster. Also, be careful when making optimizations that memory states are followed.
**Action:** Replaced `pathlib.Path.rglob()` with custom `fast_rglob` using `os.scandir` for faster recursive file searches across the codebase.

## 2026-06-26 - [Optimization using fast_rglob]
**Learning:** `pathlib.Path.rglob()` is slow due to creating intermediate Path objects. Using `os.scandir` is much faster. Also, be careful when making optimizations that memory states are followed.
**Action:** Replaced `pathlib.Path.rglob()` with custom `fast_rglob` using `os.scandir` for faster recursive file searches across the codebase.
