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
_ALLOWED_HIDDEN_DIRS = frozenset({".env", ".gitignore"})


def _iter_files_fast(search_path: str) -> Iterator[str]:
    """Internal fast file traversal using strings."""
    try:
        with os.scandir(search_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        name = entry.name
                        # Skip hidden directories (except .env, .gitignore)
                        if name.startswith(".") and name not in _ALLOWED_HIDDEN_DIRS:
                            continue
                        if name in _SKIP_DIRS:
                            continue
                        yield from _iter_files_fast(entry.path)
                    elif entry.is_file():
                        yield entry.path
                except OSError:
                    continue
    except OSError:
        return


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    for path in _iter_files_fast(str(search_path)):
        yield Path(path)
