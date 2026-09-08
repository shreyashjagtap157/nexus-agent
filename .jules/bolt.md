
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-09-08 - [Avoid os.walk with explicit dir exclusion lists in favor of iter_files]
**Learning:** Using `os.walk` and manually pruning `dirs[:]` based on custom exclusion sets is noticeably slower than using the centralized `iter_files` utility (which relies on `os.scandir` under the hood). `iter_files` skips the overhead of generating lists for entire directory structures and directly yields valid `Path` objects, which eliminates the bottleneck of repeatedly calling `Path(root)` inside nested loops.
**Action:** When scanning the workspace (e.g., in tools or scanners), always prefer `iter_files(workspace, exclude_dirs=...)` from `nexus_agent.utils.fs` over `os.walk`, ensuring `include_hidden=True` is passed if original behavior traversed hidden files.
