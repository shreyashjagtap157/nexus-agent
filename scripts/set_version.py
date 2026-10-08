#!/usr/bin/env python3
"""Bump the repository-wide NexusAgent version from one canonical value.

This utility updates only the files governed by docs/VERSIONING.md and finishes
by running the same synchronization validator used by CI.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

TARGETS = (
    ("pyproject.toml", lambda version: f'version = "{version}"'),
    ("src/nexus_agent/__init__.py", lambda version: f'__version__ = "{version}"'),
    ("nexus-rs/Cargo.toml", lambda version: f'version = "{version}"'),
    ("nexus-desktop/Cargo.toml", lambda version: f'version = "{version}"'),
    ("config/default.yaml", lambda version: f'version: "{version}"'),
    ("src/nexus_agent/_default_config.yaml", lambda version: f'version: "{version}"'),
)


def validate(version: str) -> None:
    if not SEMVER.fullmatch(version.strip()):
        raise SystemExit(f"Invalid SemVer: {version!r}")


def replace_unique(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path.relative_to(ROOT)}: expected exactly one version marker, found {count}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="New SemVer, e.g. 0.3.0-alpha.4")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    version = args.version.strip()
    validate(version)

    current = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    validate(current)
    if current == version:
        print(f"Already at {version}.")
        return 0

    # Published versions are immutable. A clean tag check prevents accidental
    # relabeling when the script is run in a release checkout.
    try:
        tags = subprocess.run(
            ["git", "tag", "--list", f"v{version}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        tags = ""
    if tags:
        raise SystemExit(f"Release tag v{version} already exists; published versions are immutable.")

    if args.dry_run:
        print(f"Would bump {current} -> {version}")
        for relative, _ in TARGETS:
            print(f"  {relative}")
        print("  VERSION")
        print("  nexus-rs/Cargo.lock package nexus")
        return 0

    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")

    old_pyproject = f'version = "{current}"'
    old_runtime = f'__version__ = "{current}"'
    old_rs = f'version = "{current}"'
    old_yaml = f'version: "{current}"'
    for relative, marker_factory in TARGETS:
        path = ROOT / relative
        marker = old_runtime if relative.endswith("__init__.py") else (
            old_yaml if relative.endswith(".yaml") else old_pyproject
        )
        replace_unique(path, marker, marker_factory(version))

    lock_path = ROOT / "nexus-rs/Cargo.lock"
    lock_text = lock_path.read_text(encoding="utf-8")
    old_lock = f'name = "nexus"\\nversion = "{current}"'
    new_lock = f'name = "nexus"\\nversion = "{version}"'
    if lock_text.count(old_lock) != 1:
        raise SystemExit("nexus-rs/Cargo.lock: expected exactly one nexus package version marker")
    lock_path.write_text(lock_text.replace(old_lock, new_lock), encoding="utf-8")

    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_version.py")],
        cwd=ROOT,
        check=False,
    )
    if check.returncode != 0:
        raise SystemExit("Version synchronization check failed after update.")
    print(f"Bumped NexusAgent {current} -> {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
