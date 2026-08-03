
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-05-18 - Fix f-string syntax error for Python 3.10 and 3.11\n**Learning:** Reusing outer quote characters in f-strings is a Python 3.12 feature and causes `SyntaxError` in Python 3.10 and 3.11.\n**Action:** Use different quote characters inside f-string expressions or construct the string separately.
