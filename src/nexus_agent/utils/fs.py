import os
from collections.abc import Iterator
from pathlib import Path

# Use frozenset for O(1) lookups and define it at module level
# to prevent re-allocating the set on every recursive call.
_SKIP_DIRS = frozenset(
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


def iter_files(search_path: Path | str) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                            continue
                        if entry.name in _SKIP_DIRS:
                            continue

                        # Pass string paths directly during recursion to avoid the overhead
                        # of continuously allocating intermediate pathlib.Path objects.
                        yield from iter_files(entry.path)
                    elif entry.is_file():
                        # Only convert to Path at the leaf nodes before yielding
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return
