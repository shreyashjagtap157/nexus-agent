import os
from collections.abc import Iterator
from pathlib import Path


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


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """
    Lazily iterate ALL files, directories, and symlinks under search_path using a
    non-recursive os.scandir stack. This behaves similarly to pathlib.rglob('*') but
    is significantly faster and avoids OOM and RecursionError on deep directory trees.
    """
    stack = [str(search_path)]
    while stack:
        current_path = stack.pop()
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        # Yield every entry (file, directory, symlink) to match rglob('*')
                        yield Path(entry.path)
                        # Only push directories to the stack to recurse into them
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue
