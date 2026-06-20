import fnmatch
import os
from collections.abc import Generator
from pathlib import Path


def fast_rglob(path: Path | str, pattern: str = "*") -> Generator[Path, None, None]:
    """
    Recursively yield files matching pattern in the given path, using os.scandir for performance.
    Avoids pathlib.rglob overhead.
    """
    if isinstance(path, Path):
        path = str(path)

    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        yield from fast_rglob(entry.path, pattern)
                    elif entry.is_file(follow_symlinks=True):
                        if fnmatch.fnmatch(entry.name, pattern):
                            yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        pass
    except OSError:
        pass
