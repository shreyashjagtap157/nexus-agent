import fnmatch
import os
from collections.abc import Iterator


def fast_rglob(directory: str | os.PathLike, pattern: str) -> Iterator[str]:
    """
    Fast recursive glob using os.scandir.
    Skips common hidden/build directories to vastly improve performance over pathlib.rglob.
    Yields string paths to avoid the overhead of creating intermediate Path objects.
    """
    skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}

    def _scandir_recursive(path: str) -> Iterator[str]:
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip common hidden directories and build artifacts
                            if entry.name in skip_dirs or (
                                entry.name.startswith(".")
                                and entry.name not in {".env", ".gitignore"}
                            ):
                                continue
                            yield from _scandir_recursive(entry.path)
                        elif entry.is_file(follow_symlinks=True):
                            if fnmatch.fnmatch(entry.name, pattern):
                                yield entry.path
                    except OSError:
                        continue
        except OSError:
            pass

    yield from _scandir_recursive(str(directory))
