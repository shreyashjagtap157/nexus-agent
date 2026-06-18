
## 2024-06-15 - [Replace slow pathlib.rglob with fast os.scandir for directory traversals]
**Learning:** Using `pathlib.Path.rglob()` for recursive directory traversal creates significant overhead because it creates intermediate `Path` objects. A custom recursive `os.scandir` implementation is much faster for tasks like finding GGUF files and calculating disk usage, especially when handling deeply nested folders.
**Action:** When optimizing file system traversal or repeated `stat` checking in hot loops, prefer `os.scandir` with explicit `follow_symlinks` flags instead of `pathlib.rglob()`.

## 2024-10-24 - [Avoid pathlib.rglob for file searching to prevent object creation overhead]
**Learning:** We replaced multiple instances of `pathlib.Path.rglob` with our custom `fast_rglob` built on `os.scandir` in `src/nexus_agent/__main__.py`, `src/nexus_agent/cli/commands/session_mixin.py`, and `src/nexus_agent/cli/commands/interactive_ui.py`. These traversals happen inside of interactive TUI flows, so taking less time to load file matches makes the interface feel noticeably snappier, especially on deeply-nested workspaces. Using `os.scandir` avoiding creating many intermediary pathlib Path objects, generating Paths only for matched files.
**Action:** When finding files or filtering via glob, always use the `fast_rglob` helper from `src.nexus_agent.utils.fs` rather than `pathlib.rglob` for substantial speedups.
