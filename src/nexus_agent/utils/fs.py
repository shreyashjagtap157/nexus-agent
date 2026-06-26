import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path


def fast_rglob(path: str | Path, pattern: str = "*", ignore_hidden: bool = False) -> Iterator[Path]:
    """Fast recursive glob using os.scandir to avoid pathlib.rglob overhead."""
    try:
        with os.scandir(str(path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if ignore_hidden and entry.name.startswith("."):
                            continue
                        yield from fast_rglob(entry.path, pattern, ignore_hidden)
                    elif entry.is_file(follow_symlinks=True):
                        if ignore_hidden and entry.name.startswith("."):
                            continue
                        if fnmatch.fnmatch(entry.name, pattern):
                            yield Path(entry.path)
                except OSError:
                    continue
    except OSError:
        pass
