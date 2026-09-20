
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-09-20 - [Replace slow os.walk with fast os.scandir wrapper iter_files]
**Learning:** `os.walk` aggressively aggregates all directory entries into lists before yielding them, which can cause significant memory overhead and slowness in repositories with deeply nested structures.
**Action:** When optimizing file system traversal or recursive directory scanning, replace standard `os.walk` usage with a lazy `os.scandir`-backed utility function (like `iter_files`). Ensure the replacement wrapper accepts `exclude_dirs` and `include_hidden` arguments to perfectly emulate `os.walk`'s directory filtering and hidden file traversal behaviors.

## 2024-09-20 - [Fixing test dependencies in mocking]
**Learning:** In tests patching `sys.modules` to simulate missing dependencies (e.g. `{"openvino": None}`), ensure the key perfectly matches the exact dependency module explicitly checked in the codebase (e.g. `openvino`). Copy/paste errors (like reusing `{"jax": None}`) lead to `AssertionError` failures because the code correctly imports the unmocked target module (e.g. `openvino`).
**Action:** When mocking or simulating missing external dependencies for fallback testing, carefully verify the module key name in `patch.dict('sys.modules')` against the target code's import statements.
