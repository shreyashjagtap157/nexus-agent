
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-08-18 - [Replace recursive os.scandir with iterative stack for deep directory traversals]
**Learning:** While replacing `pathlib.rglob()` with a recursive `os.scandir` implementation avoids intermediate `Path` object overhead, deep recursion using `os.scandir` can still cause `Too many open files` errors (FD exhaustion) or hit Python's maximum recursion depth, because the file descriptor for the parent directory remains open while recursively scanning subdirectories.
**Action:** When implementing manual `os.scandir` directory traversals, always use an iterative stack-based approach instead of recursion. This ensures the iterator is closed for a directory before processing its children, keeping the number of concurrently open file descriptors to a minimum.
## 2024-08-18 - [Fix TimeoutExpired exception in subprocess call for NPU detection]
**Learning:** When using `subprocess.run` to call an external tool for hardware detection (like a powershell command), passing a `timeout` argument means the call can raise `subprocess.TimeoutExpired`. If it's uncaught, it will crash the app or fail the tests, especially in CI environments where these commands can take unusually long to run.
**Action:** When using `subprocess.run` with a `timeout` argument, always ensure that `subprocess.TimeoutExpired` is handled in the `except` block.
