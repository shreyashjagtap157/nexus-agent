
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Lazy Generator Evaluation for rglob]
**Learning:** Using greedy list comprehensions like `[str(f) for f in rglob("*.py")][:20]` completely negates the memory benefits of the `rglob()` generator. It evaluates the entire traversal before slicing, potentially causing severe memory spikes (OOM) and lag on large repositories.
**Action:** When slicing generators like `rglob`, always use lazy evaluation such as `itertools.islice(generator, limit)` instead of evaluating into a list first.
