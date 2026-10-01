
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-01 - [Avoid Path instantiation and set recreation in recursive traversal loops]
**Learning:** In deeply recursive directory traversal functions (like `iter_files` wrapping `os.scandir`), creating `set` objects inside the loop and instantiating `Path` objects for intermediate directories introduces measurable instantiation overhead (e.g., ~7% slowdown on large trees).
**Action:** When writing recursive `os.scandir` walkers, hoist static exclusion lists into module-level `frozenset` constants and pass paths as raw strings through the recursion, only wrapping the final yielded file paths in `Path` objects.
