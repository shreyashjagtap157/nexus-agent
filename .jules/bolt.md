
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2026-09-07 - [Replace os.walk with optimized os.scandir wrapper iter_files]
**Learning:** Using os.walk for full repository scans creates significant memory overhead and slowness due to in-memory buffering of entire directories before yielding. The custom iter_files() wrapper uses os.scandir for lazy loading and avoids large list allocations.
**Action:** When performing full repository scans, replace os.walk with the iter_files utility from nexus_agent.utils.fs, passing exclude_dirs appropriately.
## 2024-05-18 - [Simulating Missing Dependencies in CI Tests]
**Learning:** Using patch.dict('sys.modules', {'openvino': None}) to simulate missing optional dependencies in tests failed consistently on GitHub Actions CI for macos/windows runners, resulting in AssertionError: 1 != 0 because the mocked module wasn't reliably triggering ImportError in the module under test.
**Action:** When testing optional dependencies, implement a context manager using a custom ImportBlocker inside sys.meta_path to intercept find_spec and reliably raise ImportError across all environments.
## 2024-05-18 - [Preventing subprocess timeouts during CLI wizard testing]
**Learning:** Testing CLI wizards (like SetupWizard) that rely on hardware detection functions (e.g., ModelManager.detect_hardware) can cause subprocess.TimeoutExpired exceptions in CI environments if the detection invokes real shell commands (like powershell Get-CimInstance).
**Action:** Always mock hardware detection functions when testing CLI commands or wizards to prevent subprocess hangs. Ensure the mock returns a dictionary with expected hardware keys to prevent UI rendering errors.
