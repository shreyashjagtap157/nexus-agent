
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-07-25 - [Lazy evaluation of rglob with islice]
**Learning:** Greedily evaluating `rglob()` into a list before slicing (e.g., `[str(f) for f in path.rglob("*.py")][:20]`) causes severe performance bottlenecks in large directories like workspaces with virtual environments, as it loads all matches into memory before taking the first 20.
**Action:** Use `itertools.islice` (e.g., `itertools.islice(path.rglob("*.py"), 20)`) to lazily consume generators and limit evaluation, preventing full directory scans.
