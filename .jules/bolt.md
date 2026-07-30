## 2026-07-30 - Lazy Evaluation Over pathlib.rglob

**Learning:** `pathlib.Path.rglob()` is incredibly slow in this project because it eagerly instantiates `Path` objects and recursively traverses the entire file tree, including massive ignored directories like `.git`, `node_modules`, and `.venv`.
**Action:** When searching for files locally, replace `rglob` with a custom `os.scandir` generator (e.g., `_fast_rglob_py`) that maintains a stack, explicitly skips heavy ignored directories (`follow_symlinks=False`), and uses `itertools.islice` to terminate early once the desired number of matches (e.g., 20) is found.
