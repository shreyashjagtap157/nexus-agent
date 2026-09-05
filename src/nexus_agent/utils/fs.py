import os
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SKIP_DIRS = frozenset({
    "node_modules",
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
})

def iter_files(
    search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    skip_set = DEFAULT_SKIP_DIRS
    if exclude_dirs:
        skip_set = skip_set.union(exclude_dirs)

    def _iter(current_path: Path) -> Iterator[Path]:
        try:
            with os.scandir(str(current_path)) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if (
                                not include_hidden
                                and entry.name.startswith(".")
                                and entry.name not in {".env", ".gitignore"}
                            ):
                                continue
                            if entry.name in skip_set:
                                continue
                            yield from _iter(Path(entry.path))
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            return

    yield from _iter(search_path)
