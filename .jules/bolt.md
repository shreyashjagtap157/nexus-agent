
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2025-02-28 - [Eliminate Path object creation in recursive directory traversal]
**Learning:** Creating `pathlib.Path` objects and sets within a hot recursive traversal loop (like in `iter_files`) adds significant overhead. Passing raw strings through recursive `os.scandir` calls and using global `frozenset` constants for lookup sets drastically reduces instantiation overhead.
**Action:** When implementing recursive directory traversals with `os.scandir`, keep paths as raw strings as long as possible, declaring static lookup sets as global `frozenset`s outside the function, and only convert to `pathlib.Path` right before yielding the final result.
