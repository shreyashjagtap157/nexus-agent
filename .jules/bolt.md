
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-16 - [Optimize iter_files by reducing Path instantiation in recursive loops]
**Learning:** Instantiating `pathlib.Path` objects for every intermediate directory in recursive `os.scandir` traversals adds significant overhead. Passing raw strings between recursive calls and converting to `Path` only when yielding final files is much faster.
**Action:** When implementing custom recursive directory traversals, pass raw string paths internally and extract static lookup collections into global `frozenset` constants.
