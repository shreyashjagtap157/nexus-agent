import os
from pathlib import Path


def iter_files(search_path: Path):
    """Lazily iterate files under search_path using os.scandir to avoid OOM from rglob."""
    try:
        # Use an explicit stack instead of recursion to avoid limits and function call overhead
        stack = [str(search_path)]
        while stack:
            current_path = stack.pop()
            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                # Skip hidden directories (except .env, .gitignore)
                                if entry.name.startswith(".") and entry.name not in {
                                    ".env",
                                    ".gitignore",
                                }:
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
                                stack.append(entry.path)
                            elif entry.is_file():
                                yield Path(entry.path)
                        except OSError:
                            continue
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
