
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-11-25 - [Use itertools.islice for lazy evaluation of file traversals]
**Learning:** Using list comprehensions with array slicing (e.g. `[f for f in Path.rglob("*")][:20]`) on generators like `pathlib.rglob` forces the entire generator to evaluate into memory before slicing, which causes significant performance overhead and potential OOM issues on large directories.
**Action:** When only a specific number of items are needed from a generator or file traversal, use lazy consumption with `itertools.islice` (e.g. `[f for f in itertools.islice(Path.rglob("*"), 20)]`) to evaluate only the required elements.
