import os
from collections.abc import Iterator
from pathlib import Path


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir with a stack
    to avoid recursion limits.
    Provides significantly better performance than pathlib.rglob.
    """
    stack = [str(search_path)]
    skip_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"}

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if entry.name.startswith(".") and entry.name not in {
                                ".env",
                                ".gitignore",
                            }:
                                continue
                            if entry.name in skip_dirs:
                                continue
                            stack.append(entry.path)
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue
