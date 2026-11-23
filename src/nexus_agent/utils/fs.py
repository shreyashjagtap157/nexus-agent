import os
from collections.abc import Iterator
from pathlib import Path


def iter_files(search_path: Path) -> Iterator[Path]:
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    try:
        with os.scandir(str(search_path)) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip hidden directories (except .env, .gitignore)
                        if entry.name.startswith(".") and entry.name not in {".env", ".gitignore"}:
                            continue
                        skip_dirs = {
                            "node_modules",
                            "__pycache__",
                            ".git",
                            "venv",
                            ".venv",
                            "dist",
                            "build",
                        }
                        if entry.name in skip_dirs:
                            continue
                        yield from iter_files(Path(entry.path))
                    elif entry.is_file():
                        yield Path(entry.path)
                except OSError:
                    continue
    except PermissionError:
        return
    except OSError:
        return


def iter_all_files(search_path: Path) -> Iterator[Path]:
    """Non-recursive, stack-based traversal yielding all entries including dirs/symlinks."""
    stack = [search_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(str(current)) as it:
                # Sort entries alphabetically to ensure consistent, deterministic behavior
                # across operating systems (e.g. Windows vs Linux) for tests and clients.
                entries = list(it)
                entries.sort(key=lambda e: e.name)

                dirs_to_append = []
                for entry in entries:
                    try:
                        p = Path(entry.path)
                        yield p
                        if entry.is_dir(follow_symlinks=False):
                            dirs_to_append.append(p)
                    except OSError:
                        continue

                # Reverse the directories before appending to the stack so they are popped
                # and processed in alphabetical order.
                dirs_to_append.reverse()
                stack.extend(dirs_to_append)
        except OSError:
            continue
