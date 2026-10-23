
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-23 - [Optimize pathlib sorting with string conversion]
**Learning:** Sorting `pathlib.Path` objects directly has hidden overhead because `Path.__lt__` internally builds tuples for comparison. Changing the sort key to the string representation of the path provides a significant micro-optimization, as Python string comparisons are executed very quickly in C.
**Action:** When sorting lists containing `pathlib.Path` objects in performance-sensitive code, use `str(path)` as the sort key instead of the `Path` object itself.
