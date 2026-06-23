import os
import fnmatch
from pathlib import Path
from typing import Iterator

def fast_rglob(directory: str | Path, pattern: str) -> Iterator[Path]:
    """
    Recursively yield files matching the pattern using os.scandir.

    ⚡ Bolt Optimization:
    Avoids creating intermediate Path objects for every directory compared to
    pathlib.rglob. This significantly speeds up file traversal when dealing
    with deeply nested folders and prevents large memory overhead.

    Uses follow_symlinks=True for files and False for directories.
    """
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                            continue
                        skip_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"}
                        if entry.name in skip_dirs:
                            continue
                        yield from fast_rglob(entry.path, pattern)
                    elif entry.is_file(follow_symlinks=True):
                        if fnmatch.fnmatch(entry.name, pattern) or fnmatch.fnmatch(entry.path, pattern):
                            yield Path(entry.path)
                except OSError:
                    continue
    except OSError:
        pass
