from pathlib import Path
import subprocess
import sys


def test_version_contract_script_passes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_version.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr



def test_canonical_version_is_alpha_snapshot_and_synchronized():
    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))*)?",
        version,
    )
    assert "-alpha." in version or "-beta." in version or "-rc." in version or version.startswith("0.")
    for path, marker in (
        ("pyproject.toml", f'version = "{version}"'),
        ("src/nexus_agent/__init__.py", f'__version__ = "{version}"'),
        ("nexus-rs/Cargo.toml", f'version = "{version}"'),
        ("nexus-desktop/Cargo.toml", f'version = "{version}"'),
        ("config/default.yaml", f'version: "{version}"'),
        ("src/nexus_agent/_default_config.yaml", f'version: "{version}"'),
    ):
        assert marker in (root / path).read_text(encoding="utf-8")
