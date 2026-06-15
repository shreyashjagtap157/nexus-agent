
## 2024-06-15 - Fast Directory Traversal with os.scandir
**Learning:** `pathlib.Path.rglob()` creates an intermediate `Path` object for every file and directory it encounters, which is a significant overhead when scanning large directories or multiple times.
**Action:** When optimizing hot loops involving file system traversal or sizing, replace `pathlib.Path.rglob` or `.glob` with a custom recursive traversal using `os.scandir()`. Ensure `follow_symlinks=True` is used for files to mimic standard `.rglob()` symlink resolution, while keeping `follow_symlinks=False` for directories to prevent infinite recursion.
