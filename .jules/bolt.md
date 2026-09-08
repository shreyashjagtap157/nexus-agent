
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2026-09-08 - [Mocking openvino dependency correctly in tests]
**Learning:** When patching `sys.modules` to simulate missing dependencies (e.g., `openvino`), ensure the mocked dictionary key exactly matches the module being tested. I incorrectly used `jax` instead of `openvino` for `test_no_openvino`, causing the test to fail.
**Action:** Double-check the module name being patched in `patch.dict('sys.modules', {<module_name>: None})` aligns with the function under test.
