## 2023-09-04 - iter_files Optimization

**Learning:** `os.walk` with in-place list modification (`dirs[:] = [...]`) is significantly slower than using `os.scandir` directly, especially in large repositories with many nested directories like virtual environments or `node_modules`. Building and pruning the list of directories in memory creates a bottleneck.
**Action:** Always prefer `iter_files(workspace, exclude_dirs=...)` over `os.walk(workspace)` for recursive directory traversal when exclusions are needed. Ensure `iter_files` is imported from `nexus_agent.utils.fs`.
