
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-08-10 - Resolve f-string and missing import syntax errors blocking python versions < 3.12 CI
**Learning:** Be very careful to verify and run tests not just locally (Python 3.12 or 3.13) but for older python versions. Using backslashes inside f-string expressions is a feature available from Python 3.12. For older versions like Python 3.10 and 3.11, backslashes inside f-string expressions result in a SyntaxError. Furthermore, always make sure to import required modules before referencing them to prevent `NameError`.
**Action:** Before running tests or deploying on cross version platforms (CI suites), double check syntax usage compatibility on different Python versions. When generating code dynamically or applying regex patches, thoroughly test using local runners to surface undefined imports (`NameError`) before submitting changes.
