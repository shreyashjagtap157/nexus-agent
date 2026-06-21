import fnmatch
import os
from pathlib import Path
from typing import Iterator

def fast_rglob(directory: Path | str, pattern: str) -> Iterator[Path]:
    """
    Fast recursive glob using os.scandir.
    Yields Path objects matching the pattern.

    Performance Optimization:
    Uses os.scandir instead of pathlib.rglob to avoid creating intermediate
    Path objects for every file in the directory tree.
    """
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    yield from fast_rglob(entry.path, pattern)
                elif entry.is_file(follow_symlinks=True):
                    if fnmatch.fnmatch(entry.name, pattern):
                        yield Path(entry.path)
    except PermissionError:
        pass
    except OSError:
        pass
