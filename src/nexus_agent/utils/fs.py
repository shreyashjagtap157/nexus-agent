import os
from collections.abc import Iterator
from pathlib import Path


def iter_files(search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False) -> Iterator[Path]:  # noqa: E501
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob.

    ⚡ Bolt Optimization: Uses os.scandir instead of os.walk or rglob.
    os.scandir is significantly faster as it caches file attributes and
    yields entries immediately rather than building lists in memory.
    """
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

    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if not include_hidden and entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:  # noqa: E501
                            continue
                        if entry.name in skip_dirs:
                            continue
                        yield from iter_files(Path(entry.path), exclude_dirs, include_hidden)
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
