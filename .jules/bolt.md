
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - [Optimize custom iter_files and replace slow os.walk implementations]
**Learning:** Python's `os.walk` iterates efficiently but custom recursive generator wrappers (like `iter_files`) can introduce significant overhead if variables (like sets or skip lists) are dynamically instantiated during each recursion, negating the memory efficiency of `os.scandir`.
**Action:** Lift static default skip lists to the module level as `frozenset`. Pre-calculate dynamically requested skipped directories before defining the recursive generator. Expose configuration flags (like `include_hidden`) in `iter_files` so that it can directly replace the less memory-efficient `os.walk` calls across the codebase without causing regressions in functionality.
