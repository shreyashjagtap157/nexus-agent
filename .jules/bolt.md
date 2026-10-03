
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-10-03 - SQLite N+1 Update queries in loops
**Learning:** In `nexus-agent/memory/long_term.py`, iterating over `conn.execute("SELECT ...")` and executing an `UPDATE` query per row inside the loop (especially when doing another `SELECT` query first if missing data) degrades performance severely as database size grows.
**Action:** When updating rows iteratively in Python SQLite, batch the updates by gathering data in a local array/list, pulling all necessary column data in the initial `SELECT`, and applying `conn.executemany("UPDATE ...", data)` outside the loop.
