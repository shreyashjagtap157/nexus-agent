
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-07-25 - [Optimize os.scandir with raw strings and frozensets]
**Learning:** While `os.scandir` avoids `Path.rglob()` overhead, instantiating `Path` objects and redundant `set` allocations within deep recursive directory traversals still adds significant overhead. Passing raw strings through recursive generator calls and using static global `frozenset` objects speeds up traversal significantly.
**Action:** When writing recursive file system traversal loops, pass paths as raw strings through the recursive calls instead of `pathlib.Path` objects, and declare static lookup sets as global `frozenset` constants outside the function to eliminate instantiation overhead, converting to `Path` only when yielding final results.
