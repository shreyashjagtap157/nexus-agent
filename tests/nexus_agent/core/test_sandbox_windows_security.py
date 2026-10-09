from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import nexus_agent.core.sandbox as sandbox_module
from nexus_agent.core.sandbox import Sandbox, SandboxConfig, SandboxMode


def make_auto_sandbox(workspace: Path) -> Sandbox:
    return Sandbox(
        config=SandboxConfig(mode=SandboxMode.AUTO),
        workspace=workspace,
    )


def test_windows_external_process_never_uses_cmd_exe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    monkeypatch.setattr(
        sandbox_module.shutil,
        "which",
        lambda _name: r"C:\Windows\System32\whoami.exe",
    )
    sandbox = make_auto_sandbox(tmp_path)
    completed = subprocess.CompletedProcess(
        args=["whoami", "/all", "&", "calc.exe"],
        returncode=0,
        stdout="safe output\n",
        stderr="",
    )

    with patch.object(sandbox_module.subprocess, "run", return_value=completed) as run:
        result = sandbox.execute("whoami /all & calc.exe")

    assert result.returncode == 0
    argv = run.call_args.args[0]
    assert argv == ["whoami", "/all", "&", "calc.exe"]
    assert argv[0].lower() != "cmd.exe"
    assert "calc.exe" in argv


@pytest.mark.parametrize(
    "command",
    [
        "cmd.exe /c whoami",
        "cmd /k whoami",
        "powershell.exe -Command whoami",
        "pwsh -EncodedCommand d2hvYW1p",
    ],
)
def test_windows_shell_launchers_are_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    sandbox = make_auto_sandbox(tmp_path)

    with patch.object(sandbox_module.subprocess, "run") as run:
        result = sandbox.execute(command)

    assert result.returncode == -1
    assert result.was_approved is False
    assert "Execution denied" in result.stderr
    run.assert_not_called()


def test_windows_batch_scripts_are_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    monkeypatch.setattr(
        sandbox_module.shutil,
        "which",
        lambda _name: r"C:\tools\npm.cmd",
    )
    sandbox = make_auto_sandbox(tmp_path)

    with patch.object(sandbox_module.subprocess, "run") as run:
        result = sandbox.execute("npm.cmd install")

    assert result.returncode == -1
    assert "batch files are not executed" in result.stderr
    run.assert_not_called()


def test_windows_echo_treats_shell_metacharacters_as_plain_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    sandbox = make_auto_sandbox(tmp_path)

    with patch.object(sandbox_module.subprocess, "run") as run:
        result = sandbox.execute("echo hello & whoami")

    assert result.returncode == 0
    assert result.stdout == "hello & whoami\n"
    run.assert_not_called()


def test_windows_type_can_read_workspace_file_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    target = tmp_path / "safe.txt"
    target.write_text("safe contents", encoding="utf-8")
    result = make_auto_sandbox(tmp_path).execute('type "safe.txt"')

    assert result.returncode == 0
    assert result.stdout == "safe contents"


def test_windows_type_cannot_read_outside_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    outside = tmp_path.parent / f"{tmp_path.name}-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        result = make_auto_sandbox(tmp_path).execute(f'type "{outside}"')
    finally:
        outside.unlink(missing_ok=True)

    assert result.returncode == 1
    assert "outside workspace boundary" in result.stderr


def test_windows_dir_lists_only_workspace_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_module.sys, "platform", "win32")
    (tmp_path / "visible.txt").write_text("x", encoding="utf-8")
    result = make_auto_sandbox(tmp_path).execute("dir")

    assert result.returncode == 0
    assert "visible.txt" in result.stdout
    assert result.stdout.endswith("\n")
