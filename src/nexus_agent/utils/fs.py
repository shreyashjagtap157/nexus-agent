import os
from collections.abc import Iterator
from pathlib import Path


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """
    Yields all paths (files, directories, and symlinks) under search_path.
    This replaces pathlib.Path.rglob() with a stack-based, non-recursive
    os.scandir implementation. It improves performance by avoiding
    RecursionError for deeply nested directories and reducing intermediate
    Path object allocations during the walk. It yields every Path entry
    before adding directories to the stack, avoiding functional regressions
    by keeping all hidden files and symlinks.
    """
    stack = [search_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(str(current)) as it:
                for entry in it:
                    try:
                        path_obj = Path(entry.path)
                        yield path_obj
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
