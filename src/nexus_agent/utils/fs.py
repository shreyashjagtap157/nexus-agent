import os
from collections.abc import Iterator
from pathlib import Path

_SKIP_DIRS = frozenset(
    {
        "node_modules",
        "__pycache__",
        ".git",
        "venv",
        ".venv",
        "dist",
        "build",
    }
)

_ALLOWED_HIDDEN = frozenset(
    {
        ".env",
        ".gitignore",
    }
)


def _iter_files_str(search_path: str) -> Iterator[str]:
    try:
        with os.scandir(search_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in _ALLOWED_HIDDEN:
                            continue
                        if entry.name in _SKIP_DIRS:
                            continue
                        # Pass string paths directly down to avoid intermediate Path instantiations
                        yield from _iter_files_str(entry.path)
                    elif entry.is_file():
                        yield entry.path
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    # Optimization: Use an internal generator with string paths, extracting constant sets
    # out of the loop and avoiding repeated Path creation overhead in deep directories.
    for p in _iter_files_str(str(search_path)):
        yield Path(p)
