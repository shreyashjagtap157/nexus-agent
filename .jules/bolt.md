## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-10-10 - [Replace dict unpacking in list comprehensions with manual loops for large DB results]
**Learning:** In Python, using dictionary unpacking syntax inside a list comprehension to process large SQLite row sets is measurably slower (by ~15-20%) than a manual for-loop that converts the row to a dictionary and explicitly sets the new key. The overhead comes from the dictionary merge operation.
**Action:** When processing large database results where a derived field (like JSON parsing) needs to be added to the row dictionary, use a manual for-loop with explicit dictionary mutation instead of dictionary unpacking in a list comprehension.
