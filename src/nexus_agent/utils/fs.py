import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path


def fast_rglob(directory: str | Path, pattern: str) -> Iterator[Path]:
    """
    Fast recursive glob using os.scandir.
    Avoids creating intermediate Path objects during traversal.
    """
    dir_str = str(directory)
    try:
        with os.scandir(dir_str) as it:
            for entry in it:
                if fnmatch.fnmatch(entry.name, pattern):
                    yield Path(entry.path)

                if entry.is_dir(follow_symlinks=False):
                    yield from fast_rglob(entry.path, pattern)
    except OSError:
        pass
