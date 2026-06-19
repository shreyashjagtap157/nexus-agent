import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path


def fast_rglob(directory: str | Path, pattern: str) -> Iterator[Path]:
    """
    Faster alternative to pathlib.Path.rglob using os.scandir.
    Follows symlinks for files, but not for directories to prevent infinite recursion.
    """
    try:
        with os.scandir(str(directory)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        yield from fast_rglob(entry.path, pattern)
                    elif entry.is_file(follow_symlinks=True):
                        if fnmatch.fnmatch(entry.name, pattern):
                            yield Path(entry.path)
                except OSError:
                    continue
    except OSError:
        pass
