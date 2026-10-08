#!/usr/bin/env python3
"""Verify NexusAgent release-version synchronization and optional Git tag matching."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

def read_root_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"Invalid SemVer in VERSION: {version!r}")
    return version

def checks(version: str) -> dict[str, bool]:
    files = {
        "pyproject": (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        "python_runtime": (ROOT / "src/nexus_agent/__init__.py").read_text(encoding="utf-8"),
        "nexus_rs": (ROOT / "nexus-rs/Cargo.toml").read_text(encoding="utf-8"),
        "nexus_rs_lock": (ROOT / "nexus-rs/Cargo.lock").read_text(encoding="utf-8"),
        "nexus_desktop": (ROOT / "nexus-desktop/Cargo.toml").read_text(encoding="utf-8"),
        "default_config": (ROOT / "config/default.yaml").read_text(encoding="utf-8"),
        "packaged_default_config": (ROOT / "src/nexus_agent/_default_config.yaml").read_text(encoding="utf-8"),
    }
    patterns = {
        "pyproject": rf'^version\s*=\s*"{re.escape(version)}"\s*$',
        "python_runtime": rf'^__version__\s*=\s*"{re.escape(version)}"\s*$',
        "nexus_rs": rf'^version\s*=\s*"{re.escape(version)}"\s*        "nexus_desktop": rf'^version\s*=\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
        "default_config": rf'^\s*version:\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
        "packaged_default_config": rf'^\s*version:\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
        "nexus_rs_lock": rf'(?ms)^\[\[package\]\]\nname\s*=\s*"nexus"\nversion\s*=\s*"{re.escape(version)}"\n',
        "nexus_desktop": rf'^version\s*=\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
        "default_config": rf'^\s*version:\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
        "packaged_default_config": rf'^\s*version:\s*"{re.escape(version)}"\s*    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
,
    }
    return {
        name: bool(re.search(patterns[name], content, re.MULTILINE))
        for name, content in files.items()
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected Git tag, e.g. v0.2.0-alpha.1")
    args = parser.parse_args()
    version = read_root_version()
    results = checks(version)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise SystemExit("Version drift: " + ", ".join(failed))
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Git tag {args.tag!r} does not match VERSION v{version}")
    print(f"NexusAgent version contract: PASS ({version})")
    for name in results:
        print(f"  {name}: PASS")
    if args.tag:
        print(f"  tag: PASS ({args.tag})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
