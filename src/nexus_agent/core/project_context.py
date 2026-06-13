"""
Project context loader.

Reads project-level instruction files (`AGENTS.md`, `CLAUDE.md`,
`.nexus/AGENTS.md`, etc.) and produces a single string suitable for
injection into the agent's system prompt. Cached per workspace.

Design notes:
- Walks the workspace tree looking for matching filenames, but does NOT
  recurse into `node_modules`, `.git`, `__pycache__`, `.venv`, etc.
- Walks UP the directory chain to find rules that apply to the project as
  a whole (e.g. monorepo with `AGENTS.md` at the repo root).
- Guards against prompt injection: any file whose lowercase content
  contains a `danger_keywords` entry is skipped (and logged).
- File size cap (default 50 KB) per file; configurable via constructor.
- Caches the merged result keyed on `(workspace, mtime_signature)` so a
  file edit invalidates the cache.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


DEFAULT_RULES_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "AGENT.md",
    ".nexus-agent.md",
    "developer.md",
    ".nexus/AGENTS.md",
    ".nexus/CLAUDE.md",
    ".github/AGENTS.md",
    ".github/CLAUDE.md",
)

# Phrases that indicate a prompt-injection attempt. Conservative.
DANGER_KEYWORDS: tuple[str, ...] = (
    "ignore all previous",
    "ignore previous instructions",
    "override system prompt",
    "you are now",
    "new system instructions",
    "system override",
    "disregard prior",
    "act as",
)

# Directories we never descend into when walking the workspace.
SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "target",
    "build",
    "dist",
    ".idea",
    ".vscode",
    ".nexus-agent",
})


@dataclass(frozen=True)
class LoadedFile:
    """One file that contributed to the merged context."""

    path: str
    size: int
    sha1: str  # 8-char prefix


class ProjectContextLoader:
    """Loads + caches project instruction files for a workspace."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        rules_files: Iterable[str] = DEFAULT_RULES_FILES,
        max_bytes: int = 50_000,
        max_parent_levels: int = 5,
        walk_descendants: bool = False,
        walk_ancestors: bool = True,
        max_total_bytes: int = 200_000,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.rules_files = tuple(rules_files)
        self.max_bytes = max_bytes
        self.max_parent_levels = max_parent_levels
        self.walk_descendants = walk_descendants
        self.walk_ancestors = walk_ancestors
        self.max_total_bytes = max_total_bytes
        self._cache: tuple[str, tuple[LoadedFile, ...]] | None = None
        self._cache_signature: str | None = None

    def _signature(self) -> str:
        """Return a mtime-based signature for the workspace's rules files.

        We hash the tuple of (path, mtime_ns, size) so any edit invalidates
        the cache. We also include the loader's parameters.
        """
        files: list[tuple[str, int, int]] = []
        for path in self._candidate_paths():
            try:
                stat = path.stat()
            except (OSError, FileNotFoundError):
                continue
            files.append((str(path), stat.st_mtime_ns, stat.st_size))
        param_str = "|".join((
            str(self.max_bytes),
            str(self.max_total_bytes),
            str(self.max_parent_levels),
            str(self.walk_descendants),
            str(self.walk_ancestors),
            ",".join(self.rules_files),
        ))
        payload = f"{param_str}::{sorted(files)}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def _candidate_paths(self) -> list[Path]:
        """All candidate rules-file paths under the workspace tree + ancestors.

        We do a controlled BFS up to `max_parent_levels` to find ancestor
        files, and (optionally) a depth-limited walk to find descendants.
        """
        candidates: list[Path] = []
        # 1) Workspace root (most specific, highest priority)
        for name in self.rules_files:
            candidates.append(self.workspace / name)
        # 2) Ancestors
        if self.walk_ancestors:
            parent = self.workspace.parent
            for _ in range(self.max_parent_levels):
                if parent == parent.parent:
                    break
                for name in self.rules_files:
                    candidates.append(parent / name)
                parent = parent.parent
        # 3) Descendants (optional, depth-limited)
        if self.walk_descendants:
            candidates.extend(self._descendants(self.workspace, depth=2))
        return candidates

    def _descendants(self, root: Path, depth: int) -> list[Path]:
        out: list[Path] = []
        if depth <= 0:
            return out
        try:
            for child in root.iterdir():
                if child.is_dir():
                    if child.name in SKIP_DIRS or child.name.startswith("."):
                        # Allow explicit project subdirs like .github, .nexus
                        if child.name in (".github", ".nexus"):
                            for name in self.rules_files:
                                out.append(child / name)
                        continue
                    for name in self.rules_files:
                        out.append(child / name)
                    out.extend(self._descendants(child, depth - 1))
        except (PermissionError, OSError) as e:
            logger.debug(f"Cannot list {root}: {e}")
        return out

    def _is_safe(self, content: str) -> bool:
        lower = content.lower()
        return not any(kw in lower for kw in DANGER_KEYWORDS)

    def _read_file(self, path: Path) -> LoadedFile | None:
        try:
            stat = path.stat()
        except (OSError, FileNotFoundError):
            return None
        if stat.st_size > self.max_bytes:
            logger.warning(
                f"Skipping {path}: size {stat.st_size} > max {self.max_bytes}"
            )
            return None
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError, UnicodeDecodeError) as e:
            logger.debug(f"Skipping {path}: read error {e}")
            return None
        if not content.strip():
            return None
        if not self._is_safe(content):
            logger.warning(f"Skipping {path}: prompt-injection pattern detected")
            return None
        sha1 = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
        return LoadedFile(path=str(path), size=len(content), sha1=sha1)

    def load(self, *, force: bool = False) -> str:
        """Return the merged project-context string for injection."""
        sig = self._signature()
        if not force and self._cache is not None and self._cache_signature == sig:
            return self._cache[0]
        chunks: list[str] = []
        loaded: list[LoadedFile] = []
        total = 0
        seen_paths: set[str] = set()
        for path in self._candidate_paths():
            key = str(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            if not path.is_file():
                continue
            entry = self._read_file(path)
            if entry is None:
                continue
            if total + entry.size > self.max_total_bytes:
                logger.info(
                    f"Truncating project context at {path}: total {total + entry.size} "
                    f"> max {self.max_total_bytes}"
                )
                break
            loaded.append(entry)
            total += entry.size
            chunks.append(
                f"## PROJECT CONTEXT (from {path.name})\n{path.read_text(encoding='utf-8', errors='ignore')}"
            )
        merged = "\n\n".join(chunks)
        self._cache = (merged, tuple(loaded))
        self._cache_signature = sig
        if loaded:
            logger.info(
                f"ProjectContextLoader: loaded {len(loaded)} file(s), {total} bytes"
            )
        return merged

    def loaded_files(self) -> tuple[LoadedFile, ...]:
        """Return the list of files that contributed to the current cache."""
        if self._cache is None:
            self.load()
        return self._cache[1] if self._cache else ()

    def invalidate(self) -> None:
        """Drop the cache (e.g. after the user edits a rules file)."""
        self._cache = None
        self._cache_signature = None

    def __repr__(self) -> str:
        return f"<ProjectContextLoader workspace={self.workspace}>"


def load_project_context(workspace: str | Path, **kwargs: object) -> str:
    """Convenience: create a loader, load, and return the string."""
    return ProjectContextLoader(workspace, **kwargs).load()
