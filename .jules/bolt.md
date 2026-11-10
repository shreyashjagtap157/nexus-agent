## YYYY-MM-DD - [rglob OOM in team artifacts]
**Learning:** `Path.rglob("*")` is extremely slow and memory-intensive on large, deeply nested directories compared to `os.scandir`. However, using recursion with `os.scandir` keeps parent directory file descriptors open, causing `EMFILE` (too many open files) errors on deeply nested directories.
**Action:** Replace `Path.rglob("*")` with a non-recursive, stack-based `os.scandir` traversal to avoid `EMFILE` and improve performance while preserving functionality, ensuring hidden files and symlinks are yielded and the final list is properly sorted.
