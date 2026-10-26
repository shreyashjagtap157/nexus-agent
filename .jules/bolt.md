
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-26 - [Use non-recursive stack-based os.scandir to prevent RecursionError and EMFILE]
**Learning:** Using a custom stack-based `os.scandir` implementation avoids `RecursionError` and `EMFILE` (too many open files) errors on deeply nested directories compared to recursive approaches or `pathlib.rglob()`. When replacing `rglob('*')`, the custom generator must explicitly yield every entry (files, directories, symlinks) before conditionally appending directories to the stack to prevent functional regressions.
**Action:** Always prefer non-recursive `while stack:` approaches with `os.scandir` over recursion or `rglob('*')` when deeply nested directory traversals are required, ensuring all entries are correctly yielded.
