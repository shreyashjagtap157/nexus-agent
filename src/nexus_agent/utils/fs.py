import fnmatch
import os
from collections.abc import Generator
from pathlib import Path


def fast_rglob(path: str | Path, pattern: str) -> Generator[Path, None, None]:
    """
    Fast recursive glob using os.scandir.
    Avoids creating intermediate Path objects for better performance in hot loops.
    """
    path_str = str(path)
    try:
        with os.scandir(path_str) as it:
            for entry in it:
                if fnmatch.fnmatch(entry.name, pattern):
                    if entry.is_file(follow_symlinks=True):
                        yield Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    yield from fast_rglob(entry.path, pattern)
    except OSError:
        pass
