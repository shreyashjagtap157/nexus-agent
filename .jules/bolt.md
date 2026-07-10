
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-01-20 - [Fix blessed dependency and f-string errors causing CI crashes]
**Learning:** `blessed` caused a ModuleNotFoundError during tests but was removed in an earlier PR. The real fix for the `f-string expression part cannot include a backslash` syntax error on Python 3.10 and 3.11 is to pull the unicode characters out of the f-string formatting block, rather than reinstalling `blessed`. Furthermore, copy-pasting code with `sed` when resolving failing tests requires pinpointing the correct lines.
**Action:** When fixing Python 3.10 and 3.11 SyntaxErrors for f-strings with backslashes, explicitly extract those strings outside or use `chr()`.
