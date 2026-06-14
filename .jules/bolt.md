## 2024-06-14 - Optimize Model Discovery Hot Loop
**Learning:** Python's `pathlib.Path.rglob()` is surprisingly slow in hot loops that traverse directories with thousands of files, largely due to the overhead of instantiating an intermediate `Path` object for every single file.
**Action:** When a file system traversal loop is identified as a bottleneck, prefer using `os.scandir()` which avoids object creation overhead and provides `DirEntry` objects containing pre-fetched stat information.
