
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-01 - [Add comment to iter_files optimizations]
**Learning:** When refactoring functions or blocks, it's a rule to add comments explaining the optimization. Leaving out explanatory comments is considered a miss.
**Action:** When creating PRs, remember to include comments to describe the optimization directly in the code.
