import os
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SKIP_DIRS = frozenset({
    "node_modules",
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
})
ALLOWED_HIDDEN = frozenset({".env", ".gitignore"})

def iter_files(
    search_path: Path,
    exclude_dirs: set[str] | None = None,
    include_hidden: bool = False,
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith(".") and entry.name not in ALLOWED_HIDDEN:
                            continue
                        if entry.name in DEFAULT_SKIP_DIRS or (exclude_dirs and entry.name in exclude_dirs):
                            continue
                        yield from iter_files(Path(entry.path), exclude_dirs, include_hidden)
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
