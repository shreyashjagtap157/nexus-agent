
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-25 - [Optimize os.walk traversals with custom iter_files scandir generator]
**Learning:** `os.walk` iterates deeply over all files in a directory branch even when in-place pruning (`dirs[:] = [...]`) is utilized, resulting in unnecessary memory overhead when traversing large repos (like node_modules).
**Action:** When performing whole-directory search operations, replace `os.walk` with our centralized `iter_files` custom generator which utilizes `os.scandir` to skip exclusions efficiently before walking the branch, providing significant disk I/O performance gains.

## 2024-07-25 - [Optimize os.walk traversals with custom iter_files scandir generator]
**Learning:** `os.walk` iterates deeply over all files in a directory branch even when in-place pruning (`dirs[:] = [...]`) is utilized, resulting in unnecessary memory overhead when traversing large repos (like node_modules).
**Action:** When performing whole-directory search operations, replace `os.walk` with our centralized `iter_files` custom generator which utilizes `os.scandir` to skip exclusions efficiently before walking the branch, providing significant disk I/O performance gains.
