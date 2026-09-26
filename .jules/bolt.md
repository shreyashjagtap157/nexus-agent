
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.
## 2024-09-26 - [Optimize skip lists in os.scandir recursions]
**Learning:** When using custom recursive file traversals with `os.scandir`, re-creating `set` lookups (e.g., `skip_dirs = {"node_modules", ...}`) inside the generator yields huge memory and performance overhead per directory entry. Furthermore, continually re-instantiating `pathlib.Path` objects down the recursive call stack compounds this overhead.
**Action:** Always pre-compute skip sets as module-level `frozenset` constants. When making a recursive wrapper to return `Path` objects, use a private inner recursive generator that yields raw strings, and only cast to `Path` objects in the outermost wrapper to avoid deep instantiation costs.
## 2024-09-26 - [Mock missing optional dependencies correctly]
**Learning:** In test environments where an optional dependency (like `openvino`) is actually installed globally or natively cached in `sys.modules`, mocking `sys.modules` with an unrelated missing library key (e.g. `{"jax": None}`) to simulate the target dependency being missing does not work, because `import openvino` will still successfully resolve from the environment. This causes assertions checking for the absence of the library (like `len(runtimes) == 0`) to fail across different CI runners.
**Action:** When simulating a missing dependency in tests via `sys.modules`, explicitly map the exact module name of the target dependency to `None` (e.g. `with patch.dict("sys.modules", {"openvino": None}):`).

## 2024-09-26 - [Robustly mock missing dependencies]
**Learning:** Patching `sys.modules` with `None` to simulate a missing dependency is flaky because underlying import machinery might bypass it or natively load the C-extension in different Python environments.
**Action:** Use a side-effect mock on `builtins.__import__` to explicitly raise `ImportError("No module named X")` only when module X is requested, delegating everything else to the real `__import__`.
