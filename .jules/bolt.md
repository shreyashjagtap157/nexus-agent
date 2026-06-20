
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-20 - [Performance] Optimize python recursive file traversals with fast_rglob and itertools.islice
**Learning:** `Path.rglob` can be slow in hot loops because it allocates a `Path` object for every file and directory it traverses. Creating intermediate `Path` objects adds significant overhead. Additionally, converting an entire generator to a list (e.g. `[str(f) for f in rglob(...)][:20]`) forces the entire file tree to be evaluated before slicing, neutralizing the benefits of lazy evaluation.
**Action:** Use a custom `fast_rglob` implementation utilizing `os.scandir` to avoid intermediate `Path` objects. Combine this with `itertools.islice` to lazily evaluate the generator and stop traversing the file system as soon as the desired number of matches (e.g., 20) is found.
