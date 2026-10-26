
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-26 - [Replace rglob('*') with custom iter_all_files using os.scandir]
**Learning:** Replacing `pathlib.Path.rglob('*')` with a custom stack-based `os.scandir` implementation improves performance by avoiding `RecursionError` for deeply nested directories and reducing intermediate `Path` object allocations during the recursive walk. It must explicitly yield directories and symlinks to match `rglob('*')` behavior.
**Action:** When a full recursive file system traversal is required, prefer a custom non-recursive `os.scandir` implementation over `rglob('*')` for performance and safety on deeply nested structures.
