
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-26 - [Lazy evaluation of rglob with itertools.islice]
**Learning:** In Python, a list comprehension like `[f for f in Path.cwd().rglob("*.py")][:20]` forces the generator returned by `rglob` to fully evaluate and traverse the entire directory tree *before* taking the slice. In large projects, this causes a severe O(N) performance bottleneck and high memory usage, even if only a few items are needed.
**Action:** When slicing generators like `rglob`, always use `itertools.islice(generator, limit)` instead of list slicing to enable lazy evaluation, reducing traversal to O(1) time complexity relative to total files.
