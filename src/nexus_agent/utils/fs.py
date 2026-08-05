import os
from pathlib import Path


def fast_rglob(
    path: Path, pattern: str, max_results: int | None = 20, prefix: str | None = None
) -> list[Path]:
    """
    Fast recursive file finding using os.scandir to avoid Pathlib overhead.
    """
    results: list[Path] = []

    def _search(dir_path: str):
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
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
                        yield from _search(entry.path)
                    elif entry.is_file(follow_symlinks=True):
                        name = entry.name
                        if prefix and prefix not in name:
                            continue

                        match = False
                        if pattern.startswith("*") and pattern.endswith("*"):
                            if pattern[1:-1] in name:
                                match = True
                        elif pattern.startswith("*"):
                            if name.endswith(pattern[1:]):
                                match = True
                        elif pattern.endswith("*"):
                            if name.startswith(pattern[:-1]):
                                match = True
                        elif name == pattern:
                            match = True

                        if match:
                            yield Path(entry.path)
        except (PermissionError, OSError):
            pass

    for p in _search(str(path)):
        results.append(p)
        if max_results and len(results) >= max_results:
            break

    return results
