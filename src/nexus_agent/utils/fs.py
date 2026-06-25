import os
from collections.abc import Iterator
from pathlib import Path


def fast_rglob(directory: Path, pattern: str) -> Iterator[Path]:
    """
    Fast alternative to pathlib.Path.rglob() using os.scandir().
    Matches the behavior of rglob('*' + pattern_suffix) roughly.
    For more complex patterns, standard fnmatch might be needed.
    """
    try:
        with os.scandir(str(directory)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        yield from fast_rglob(Path(entry.path), pattern)
                    elif entry.is_file(follow_symlinks=True):
                        # Simple extension matching or partial matching
                        if pattern.startswith("*."):
                            ext = pattern[1:]
                            if entry.name.endswith(ext):
                                yield Path(entry.path)
                        elif pattern.startswith("*") and pattern.endswith("*"):
                            substring = pattern[1:-1]
                            if substring in entry.name:
                                yield Path(entry.path)
                        else:
                            import fnmatch

                            if fnmatch.fnmatch(entry.name, pattern):
                                yield Path(entry.path)
                except OSError:
                    pass
    except OSError:
        pass
