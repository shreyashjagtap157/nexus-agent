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

ALLOWED_HIDDEN_FILES = frozenset({".env", ".gitignore"})


def _iter_files_recursive(search_path: str) -> Iterator[str]:
    # Perf optimization: process recursively with string paths to avoid pathlib.Path
    # instantiations at every dir level. Sets are now global frozensets.
    try:
        with os.scandir(search_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in ALLOWED_HIDDEN_FILES:
                            continue
                        if entry.name in SKIP_DIRS:
                            continue
                        yield from _iter_files_recursive(entry.path)
                    elif entry.is_file():
                        yield entry.path
                except OSError:
                    continue
    except (PermissionError, OSError):
        return


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    # Perf optimization: only instantiate Path once per final file path
    for p in _iter_files_recursive(str(search_path)):
        yield Path(p)
