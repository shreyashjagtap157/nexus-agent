from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_bumper_updates_every_manifest_and_lockfile(tmp_path: Path) -> None:
    files = {
        "VERSION": "0.3.0-alpha.4\n",
        "pyproject.toml": 'version = "0.3.0-alpha.4"\n',
        "src/nexus_agent/__init__.py": '__version__ = "0.3.0-alpha.4"\n',
        "nexus-rs/Cargo.toml": 'version = "0.3.0-alpha.4"\n',
        "nexus-desktop/Cargo.toml": 'version = "0.3.0-alpha.4"\n',
        "config/default.yaml": 'version: "0.3.0-alpha.4"\n',
        "src/nexus_agent/_default_config.yaml": 'version: "0.3.0-alpha.4"\n',
        "nexus-rs/Cargo.lock": '[[package]]\nname = "nexus"\nversion = "0.3.0-alpha.4"\n',
    }
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for script in ("set_version.py", "check_version.py"):
        target = tmp_path / "scripts" / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "scripts" / script, target)

    result = subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / "set_version.py"), "0.3.0-alpha.5"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    actual_version = (tmp_path / "VERSION").read_text(encoding="utf-8").strip()
    assert actual_version == "0.3.0-alpha.5"
    lock = (tmp_path / "nexus-rs" / "Cargo.lock").read_text(encoding="utf-8")
    assert 'name = "nexus"\nversion = "0.3.0-alpha.5"' in lock
    check = subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / "check_version.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr
