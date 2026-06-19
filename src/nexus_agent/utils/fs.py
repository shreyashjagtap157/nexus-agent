import os
import fnmatch
from pathlib import Path
from collections.abc import Iterator

def fast_rglob(path: str | Path, pattern: str) -> Iterator[Path]:
    """
    Fast recursive file search using os.scandir to avoid Path.rglob overhead.
    Follows symlinks for files, but not for directories to prevent infinite loops.
    """
    path_str = str(path)
    if not os.path.exists(path_str):
        return

    # Check if pattern includes a path separator
    has_sep = os.sep in pattern or (os.altsep and os.altsep in pattern)

    def _walk(current_path: str) -> Iterator[Path]:
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            yield from _walk(entry.path)
                        elif entry.is_file(follow_symlinks=True):
                            # If pattern has separators, match against the relative path, otherwise just the name.
                            if has_sep:
                                # Relpath calculation is expensive, so only do it if necessary
                                rel_path = os.path.relpath(entry.path, path_str)
                                # fnmatch is cross platform, use posix paths for match string
                                if fnmatch.fnmatch(rel_path.replace(os.sep, '/'), pattern.replace(os.sep, '/')):
                                    yield Path(entry.path)
                            else:
                                if fnmatch.fnmatch(entry.name, pattern):
                                    yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError:
            return
        except OSError:
            return

    yield from _walk(path_str)
