import os
from collections.abc import Iterator
from pathlib import Path


# ⚡ Bolt Optimization: Pre-allocate standard skip directories as a global constant
# to prevent memory reallocation and dict union overhead during deep recursive traversals.
DEFAULT_SKIP_DIRS = frozenset({
    "node_modules",
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
})

def iter_files(search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False, _active_skip_dirs: frozenset[str] | None = None) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    # ⚡ Bolt Optimization: Only compute the union of skip_dirs once at the root call,
    # then pass the finalized frozenset down to recursive calls to eliminate per-directory overhead.
    if _active_skip_dirs is None:
        _active_skip_dirs = DEFAULT_SKIP_DIRS
        if exclude_dirs:
            _active_skip_dirs = _active_skip_dirs.union(exclude_dirs)

    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if not include_hidden and entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                            continue
                        if entry.name in _active_skip_dirs:
                            continue
                        yield from iter_files(Path(entry.path), exclude_dirs, include_hidden, _active_skip_dirs)
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
