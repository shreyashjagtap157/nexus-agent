## 2024-07-20 - [Fix O(N) evaluation of rglob in list comprehensions]
**Learning:** Using `[x for x in rglob()][:N]` fully evaluates the generator, loading potentially thousands of files into memory and iterating through the entire directory tree before slicing.
**Action:** When taking a slice of a generator like `rglob`, always use `itertools.islice(rglob(), N)` to enforce lazy evaluation and avoid memory and performance overhead.

## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
