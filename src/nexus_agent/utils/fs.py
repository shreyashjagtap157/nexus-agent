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


def iter_files(search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    final_skip_dirs = DEFAULT_SKIP_DIRS.union(exclude_dirs) if exclude_dirs else DEFAULT_SKIP_DIRS

    def _walk(current_path: Path) -> Iterator[Path]:
        try:
            with os.scandir(str(current_path)) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if not include_hidden and entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                                continue
                            if entry.name in final_skip_dirs:
                                continue
                            yield from _walk(Path(entry.path))
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            return

    return _walk(search_path)
