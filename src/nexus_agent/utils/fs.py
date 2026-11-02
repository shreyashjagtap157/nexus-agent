import os
from collections.abc import Iterator
from pathlib import Path


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    # Performance optimization: Replace recursion with a stack-based while loop to prevent
    # EMFILE errors (too many open files) on deeply nested directory structures and avoid
    # RecursionError.
    stack = [str(search_path)]
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
                            stack.append(entry.path)
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError:
            continue
        except OSError:
            continue


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate all entries under search_path using os.scandir."""
    # Performance optimization: Replaces pathlib.Path.rglob('*') to avoid RecursionError for deeply
    # nested directories, prevent EMFILE errors, and significantly reduce intermediate Path object
    # allocations during the traversal walk.
    stack = [str(search_path)]
    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    yield Path(entry.path)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
