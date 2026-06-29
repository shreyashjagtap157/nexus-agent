
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-25 - [Use itertools.islice for lazy evaluation of pathlib.Path.rglob]
**Learning:** Using a list comprehension to evaluate `rglob()` before slicing (e.g., `[f for f in Path.rglob("*")][:20]`) entirely defeats the purpose of the generator and forces full traversal, causing OOMs and massive slowdowns in large repositories.
**Action:** When you only need a subset of results from a file traversal or any Python generator, always use `itertools.islice()` instead of list comprehensions/slicing to enforce lazy evaluation.
