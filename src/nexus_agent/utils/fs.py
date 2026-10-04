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


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""

    def _iter_paths(current_path: str) -> Iterator[Path]:
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if entry.name.startswith(".") and entry.name not in {
                                ".env",
                                ".gitignore",
                            }:
                                continue
                            if entry.name in _SKIP_DIRS:
                                continue
                            # recursive traversal using string paths
                            yield from _iter_paths(entry.path)
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            return

    yield from _iter_paths(str(search_path))
