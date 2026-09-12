import os
from collections.abc import Iterator
from pathlib import Path

_DEFAULT_SKIP_DIRS = frozenset(
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

_ALLOWED_HIDDEN = frozenset({".env", ".gitignore"})


def iter_files(
    search_path: Path,
    exclude_dirs: set[str] | None = None,
    include_hidden: bool = False,
    _skip_dirs_cache: frozenset[str] | None = None,
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    if _skip_dirs_cache is None:
        if exclude_dirs:
            _skip_dirs_cache = frozenset(_DEFAULT_SKIP_DIRS | exclude_dirs)
        else:
            _skip_dirs_cache = _DEFAULT_SKIP_DIRS

    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if (
                            not include_hidden
                            and entry.name.startswith(".")
                            and entry.name not in _ALLOWED_HIDDEN
                        ):
                            continue
                        if entry.name in _skip_dirs_cache:
                            continue
                        yield from iter_files(
                            Path(entry.path), exclude_dirs, include_hidden, _skip_dirs_cache
                        )
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except (PermissionError, OSError):
        return
