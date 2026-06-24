import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path


def fast_rglob(
    path: str | Path, pattern: str = "*", follow_symlinks: bool = True
) -> Iterator[Path]:
    """
    Fast recursive file finding using os.scandir to avoid the memory overhead of pathlib.rglob.
    Yields Path objects matching the given pattern.
    """
    path_str = str(path)
    try:
        with os.scandir(path_str) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    # Skip common hidden/build directories for speed and memory efficiency
                    if entry.name.startswith('.') and entry.name not in {'.env', '.gitignore'}:
                        continue
                    skip_dirs = {'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build'}
                    if entry.name in skip_dirs:
                        continue
                    yield from fast_rglob(entry.path, pattern, follow_symlinks)
                elif entry.is_file(follow_symlinks=follow_symlinks):
                    if fnmatch.fnmatch(entry.name, pattern):
                        yield Path(entry.path)
    except (PermissionError, OSError):
        pass
