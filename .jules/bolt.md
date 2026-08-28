
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-08-05 - [Optimize os.walk traversals with iter_files]
**Learning:** Using `os.walk` to traverse large project directories is slow when large hidden or unneeded folders like `.venv`, `.git` and `node_modules` aren't ignored fast enough. `os.walk` loads all files/dirs per level before moving on, making it slower. Using custom generator `iter_files(workspace, exclude_dirs=...)` that utilizes `os.scandir` to recursively yield files while skipping excluded directories is significantly faster for operations like `code_intel`, `devops` and `rag_search`.
**Action:** Replace `os.walk` loops with the central `iter_files` utility from `nexus_agent.utils.fs` passing `exclude_dirs` for scalable and high-performance file traversals across large codebases.
