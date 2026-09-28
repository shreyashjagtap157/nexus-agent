
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-24 - [Avoid redundant Path instantiations and local sets in recursive traversals]
**Learning:** Inside deeply recursive functions like custom file system traversals, continually instantiating `pathlib.Path` objects and defining local `set`s (e.g., skip directories) causes unnecessary memory reallocation overhead, slowing down traversal by ~30% in benchmarks.
**Action:** When writing recursive loops over file systems, declare static lookup sets as global `frozenset` constants outside the function. Pass raw strings through the recursive steps, only converting back to `Path` when yielding the final results.
