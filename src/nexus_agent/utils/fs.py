import os
from collections.abc import Iterator
from pathlib import Path


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate all files and directories (including hidden) using stack-based os.scandir."""
    # We use a non-recursive stack-based approach with os.scandir to prevent RecursionError on
    # deeply nested directories and reduce Path object allocation overhead compared to
    # pathlib.Path.rglob('*').
    stack = [search_path]
    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(str(current_dir)) as it:
                for entry in it:
                    try:
                        path_obj = Path(entry.path)
                        yield path_obj

                        # rglob yields both files and dirs, but only traverses dirs.
                        # Do not follow symlinks.
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(path_obj)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                            continue
                        skip_dirs = {
                            "node_modules",
                            "__pycache__",
                            ".git",
                            "venv",
                            ".venv",
                            "dist",
                            "build",
                        }
                        if entry.name in skip_dirs:
                            continue
                        yield from iter_files(Path(entry.path))
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
