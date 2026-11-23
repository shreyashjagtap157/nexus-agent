import os
from collections.abc import Iterator
from pathlib import Path


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate all items under search_path using os.scandir stack.

    This optimization improves performance for large directory trees by avoiding the
    OOM and performance overhead of Path.rglob, and prevents RecursionError and
    EMFILE errors by using an iterative stack approach rather than recursion.
    """
    stack = [str(search_path)]
    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        p = Path(entry.path)
                        yield p
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
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
