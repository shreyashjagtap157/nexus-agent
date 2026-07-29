
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-05-15 - Lazy Evaluation of `rglob` Generators
**Learning:** Greedily evaluating a generator into a list inside a comprehension (e.g., `[f for f in Path.rglob("*.py")][:20]`) traverses the entire directory tree and loads all matching files into memory before slicing.
**Action:** Use lazy consumption mechanisms like `itertools.islice(generator, limit)` when limiting items from filesystem operations to drastically reduce CPU and memory usage on large repositories.
