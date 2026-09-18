
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - [Optimize custom os.walk replacements]
**Learning:** When writing performance-critical directory traversal functions (like `iter_files`), avoid modifying sets dynamically or defining large sets (`{"node_modules", ".git", ...}`) inside the recursive `_iter` function. It causes measurable reallocation overhead.
**Action:** Define constants like `DEFAULT_SKIP_DIRS` as a `frozenset` globally outside the function body.
