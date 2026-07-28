import os
from collections.abc import Iterator
from pathlib import Path


def fast_scandir(search_path: str | Path) -> Iterator[str]:
    """
    Lazily iterate files under search_path using os.scandir to avoid OOM from rglob.
    Significantly faster than pathlib.rglob.
    """
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
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
                        yield from fast_scandir(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        yield entry.path
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass
