
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-07-27 - [Avoid evaluating glob generators entirely for existence checks or slicing]
**Learning:** Greedily evaluating a generator (like `pathlib.Path.rglob()` or `glob()`) into a list in memory (e.g., via list comprehensions or `list()`) before checking for existence or slicing is a performance anti-pattern, as it iterates through all matches and can be very slow.
**Action:** Use lazy consumption like `itertools.islice(generator, limit)` for slicing, and use `any(path.glob(...))` for efficient file existence checks instead of `list(path.glob(...)) != []`.
