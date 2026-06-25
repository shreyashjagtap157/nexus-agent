import fnmatch
import os
from collections.abc import Generator
from pathlib import Path


def fast_rglob(directory: str | Path, pattern: str = "*") -> Generator[Path, None, None]:
    """
    High-performance alternative to pathlib.Path.rglob() using os.scandir.
    Avoids creating intermediate Path objects for every directory.
    Follows symlinks for files but not for directories to prevent infinite recursion.
    """

    def _scan(path_str: str) -> Generator[Path, None, None]:
        try:
            with os.scandir(path_str) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=True):
                            if fnmatch.fnmatch(entry.name, pattern):
                                yield Path(entry.path)
                        elif entry.is_dir(follow_symlinks=False):
                            yield from _scan(entry.path)
                    except OSError:
                        continue
        except OSError:
            pass

    yield from _scan(str(directory))
