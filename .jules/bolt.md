
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - Replace `rglob` with `os.scandir` via lazy generator
**Learning:** `pathlib.Path.rglob` is slow and memory-intensive for large directory trees because it instantiates Path objects for every single file indiscriminately. Evaluating generators greedily via list comprehensions like `[str(f) for f in Path.cwd().rglob("*.py")][:20]` means we process the entire tree even though we only need the first 20 results.
**Action:** Created `src.nexus_agent.utils.fs.fast_rglob` using `os.scandir` to avoid intermediate Path object overhead unless matched. Handled symlinks carefully (`follow_symlinks=True` for files, `False` for dirs to avoid recursion). Replaced list comprehensions with `itertools.islice` for true lazy evaluation.
