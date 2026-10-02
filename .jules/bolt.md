
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-10-02 - [Ensure mocked modules exactly match dependencies in tests]
**Learning:** When using `patch.dict('sys.modules', {'module_name': None})` to simulate a missing dependency in tests, ensure the mocked module name exactly matches the dependency being tested (e.g., mocking 'openvino' instead of copy-pasting a 'jax' mock). Otherwise, tests may falsely pass locally if the dependency is uninstalled in the local environment, but will fail in CI environments where the dependency is fully installed.
**Action:** Always verify the mocked module name in `patch.dict` matches the specific library being checked by the function under test.
