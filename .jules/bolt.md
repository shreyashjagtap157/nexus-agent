
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-06-25 - [Iterating over filesystem correctly]
**Learning:** Using `os.walk` is slower than , so traversing the filesystem using `os.scandir` via `iter_files` provides better performance, but always verify `skip_dirs` has correct elements.
**Action:** Replace `os.walk` in filesystem iteration scenarios with `iter_files` lazily consuming using generators.
## 2024-06-25 - [Iterating over filesystem correctly]
**Learning:** Using `os.walk` is slower than `os.scandir`, so traversing the filesystem using `os.scandir` via `iter_files` provides better performance, but always verify `skip_dirs` has correct elements.
**Action:** Replace `os.walk` in filesystem iteration scenarios with `iter_files` lazily consuming using generators.
## 2024-06-25 - [Iterating over filesystem correctly]
**Learning:** Using `os.walk` is slower than `os.scandir`, so traversing the filesystem using `os.scandir` via `iter_files` provides better performance, but always verify `skip_dirs` has correct elements.
**Action:** Replace `os.walk` in filesystem iteration scenarios with `iter_files` lazily consuming using generators.
## 2024-06-25 - [Iterating over filesystem correctly]
**Learning:** Using `os.walk` is slower than `os.scandir`, so traversing the filesystem using `os.scandir` via `iter_files` provides better performance, but always verify `skip_dirs` has correct elements.
**Action:** Replace `os.walk` in filesystem iteration scenarios with `iter_files` lazily consuming using generators.
