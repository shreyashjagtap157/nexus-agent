import os
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SKIP_DIRS = frozenset(
    {
        "node_modules",
        "__pycache__",
        ".git",
        "venv",
        ".venv",
        "dist",
        "build",
    }
)


def iter_files(
    search_path: Path, exclude_dirs: set[str] | None = None, include_hidden: bool = False
) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    skips = DEFAULT_SKIP_DIRS if exclude_dirs is None else DEFAULT_SKIP_DIRS | exclude_dirs

    def _scan(current_path: str) -> Iterator[Path]:
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Skip hidden directories (except .env, .gitignore)
                            if (
                                not include_hidden
                                and entry.name.startswith(".")
                                and entry.name not in {".env", ".gitignore"}
                            ):
                                continue
                            if entry.name in skips:
                                continue
                            yield from _scan(entry.path)
                        elif entry.is_file():
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            return

    yield from _scan(str(search_path))
