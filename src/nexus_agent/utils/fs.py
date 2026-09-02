import os
from collections.abc import Iterator
from pathlib import Path


def iter_files(search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False) -> Iterator[Path]:  # noqa: E501
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""

    # Pre-compute skip_dirs once outside the traversal loop to avoid
    # re-creating and merging the set for every single directory entry.
    skip_dirs = {
        "node_modules",
        "__pycache__",
        ".git",
        "venv",
        ".venv",
        "dist",
        "build",
    }
    if exclude_dirs:
        skip_dirs.update(exclude_dirs)

    def _iter(current_path: str) -> Iterator[Path]:
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if not include_hidden and entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:  # noqa: E501
                                continue

                            if entry.name in skip_dirs:
                                continue
                            yield from _iter(entry.path)
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError:
            return
        except OSError:
            return

    yield from _iter(str(search_path))
