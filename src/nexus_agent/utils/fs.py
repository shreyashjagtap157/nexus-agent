import os
from collections.abc import Iterator
from pathlib import Path

SKIP_DIRS = frozenset(
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

ALLOWED_HIDDEN_DIRS = frozenset({".env", ".gitignore"})


def _iter_files_raw(search_path: str) -> Iterator[str]:
    try:
        with os.scandir(search_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in ALLOWED_HIDDEN_DIRS:
                            continue
                        if entry.name in SKIP_DIRS:
                            continue
                        yield from _iter_files_raw(entry.path)
                    elif entry.is_file():
                        yield entry.path
                except OSError:
                    continue
    except OSError:
        return


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    for file_path in _iter_files_raw(str(search_path)):
        yield Path(file_path)
