import os
from collections.abc import Iterator
from pathlib import Path

_SKIP_DIRS: frozenset[str] = frozenset(
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

_ALLOWED_HIDDEN: frozenset[str] = frozenset(
    {
        ".env",
        ".gitignore",
    }
)


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""

    def _walk(path_str: str) -> Iterator[str]:
        try:
            with os.scandir(path_str) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.startswith(".") and entry.name not in _ALLOWED_HIDDEN:
                                continue
                            if entry.name in _SKIP_DIRS:
                                continue
                            yield from _walk(entry.path)
                        elif entry.is_file():
                            yield entry.path
                    except OSError:
                        continue
        except PermissionError:
            return
        except OSError:
            return

    for p in _walk(str(search_path)):
        yield Path(p)
