
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-15 - [Ensure consistent path relativity when using os.path.commonpath]
**Learning:** When substituting generic substring path-checking (which is vulnerable to partial directory name matches like `/dir_malicious` matching `/dir`) with the safer `os.path.commonpath`, you must ensure all paths passed to it are consistently absolute or relative. Passing a mix of absolute paths (e.g., from `os.path.realpath`) and relative paths (e.g., from an unresolved `str(Path)`) causes `os.path.commonpath` to raise a `ValueError: Can't mix absolute and relative paths`.
**Action:** When using `os.path.commonpath` to verify file boundaries, explicitly resolve and convert all paths to strings first (e.g., `root_str = str(root.resolve())`) to guarantee absolute paths are compared.
