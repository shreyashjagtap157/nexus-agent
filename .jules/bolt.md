
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-06-28 - [Lazy evaluate rglob with itertools.islice]
**Learning:** Even when `pathlib.Path.rglob()` returns a generator, wrapping it in a list comprehension `[str(f) for f in rglob(...)][:N]` greedily evaluates the entire traversal before slicing, causing severe performance issues on large workspaces.
**Action:** When extracting a fixed number of items from a generator, always use `itertools.islice()` to lazily evaluate and stop traversal early.
## 2024-05-18 - [SyntaxError in f-strings across Python versions]
**Learning:** Python 3.12 allows backslashes inside f-string expressions (like `f"{u2500}"`), but this is a SyntaxError in Python 3.11 and below.
**Action:** When extracting variables into f-strings, if unicode backslashes are used, assign them to variables outside the f-string or use `chr()` functions instead of raw backslash escapes to maintain compatibility across Python >= 3.10.
