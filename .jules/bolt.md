
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2025-02-14 - [Avoid `pathlib.Path` instantiation in deep recursive traversals]
**Learning:** Instantiating `pathlib.Path` objects inside a hot loop (like a recursive filesystem crawler) causes unnecessary memory overhead and slows down traversal. Furthermore, keeping static collections (like skip lists) defined inside the loop causes continuous garbage collection churn.
**Action:** Extract skip lists to module-level constants (e.g., `frozenset`). When writing custom `os.scandir` wrappers, recursively pass raw strings (`str`) instead of `Path` objects, only yielding `Path` objects at the absolute outermost layer.
## 2025-02-14 - [Mocking hardware detection in CLI tests to avoid timeouts]
**Learning:** Calling system-level processes (like `subprocess.run(["powershell", ...])`) in unit tests causes CI environments (especially Windows runners) to hang or timeout. When `ModelManager.detect_hardware()` is invoked during `SetupWizard.run()`, the test hangs.
**Action:** Always patch `detect_hardware` in tests that utilize `SetupWizard` to return static dictionary structures compatible with `rich.Table` rendering (e.g., returning strings instead of booleans for "cpu").
