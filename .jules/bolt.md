
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2025-05-15 - [Simulating Missing Dependencies in CI]
**Learning:** In CI environments where optional dependencies (like `openvino` or `jax`) are installed globally, testing "module not found" fallback paths by mocking `builtins.__import__` fails because Python skips the `__import__` call if the module is already cached in `sys.modules`.
**Action:** Always use `patch.dict("sys.modules", {"module_name": None})` to robustly simulate missing modules. Python's import machinery guarantees a `ModuleNotFoundError` if a key exists in `sys.modules` with the value `None`, bypassing any existing installations.
