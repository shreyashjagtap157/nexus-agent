import os
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SKIP_DIRS = frozenset(
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


def iter_files(
    search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    skip_set = DEFAULT_SKIP_DIRS
    if exclude_dirs:
        skip_set = skip_set.union(exclude_dirs)

    return _iter_files_impl(search_path, skip_set, include_hidden)


def _iter_files_impl(
    search_path: Path, skip_set: frozenset[str] | set[str], include_hidden: bool
) -> Iterator[Path]:
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if (
                            not include_hidden
                            and entry.name.startswith(".")
                            and entry.name not in {".env", ".gitignore"}
                        ):
                            continue
                        if entry.name in skip_set:
                            continue
                        yield from _iter_files_impl(Path(entry.path), skip_set, include_hidden)
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
