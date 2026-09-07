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

def iter_files(
    search_path: Path,
    exclude_dirs: set[str] | frozenset[str] | None = None,
    include_hidden: bool = False
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    skip_set = DEFAULT_SKIP_DIRS.union(exclude_dirs) if exclude_dirs else DEFAULT_SKIP_DIRS

    def _iter_dir(current_path: Path) -> Iterator[Path]:
        try:
            with os.scandir(str(current_path)) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if not include_hidden and entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                                continue
                            if entry.name in skip_set:
                                continue
                            yield from _iter_dir(Path(entry.path))
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except PermissionError:
            return
        except OSError:
            return

    yield from _iter_dir(search_path)
