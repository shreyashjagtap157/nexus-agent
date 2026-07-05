
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-07-05 - [Optimize Path.rglob]
**Learning:** In Python, `Path.rglob()` returns a generator. Evaluating it eagerly in a list comprehension (e.g. `[str(f) for f in Path.rglob("*.py")][:20]`) traverses the entire directory tree before slicing, which is extremely slow and memory intensive in large repositories.
**Action:** Use `itertools.islice(generator, limit)` instead for lazy evaluation to get only the necessary subset.
