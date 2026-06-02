"""
Shell Command Tool — Execute shell commands with sandbox protection.

Wraps the Sandbox class to provide a tool interface for the agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus_agent.core.sandbox import Sandbox, SandboxConfig, SandboxMode
from nexus_agent.tools.base import Tool


class ShellTool(Tool):
    """Execute shell commands in a sandboxed environment."""

    def __init__(self, workspace: Path | None = None,
                 sandbox: Sandbox | None = None,
                 sandbox_config: SandboxConfig | None = None):
        self.workspace = workspace or Path.cwd()
        config = sandbox_config or SandboxConfig(mode=SandboxMode.ASK)
        self.sandbox = sandbox or Sandbox(
            config=config,
            workspace=self.workspace,
        )

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command in the workspace. "
            "Commands are run in a sandbox with permission checks. "
            "Returns stdout, stderr, and exit code."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (optional, defaults to workspace)",
                "required": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (optional, default 60)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    @property
    def timeout(self) -> int:
        return 120

    def execute(self, command: str, cwd: str | None = None,
                timeout: int | None = None, **kwargs: Any) -> str:
        # Validate cwd stays within workspace
        if cwd:
            try:
                cwd_path = Path(cwd).resolve()
                workspace_resolved = self.workspace.resolve()
                cwd_path.relative_to(workspace_resolved)
            except ValueError:
                return f"Error: Working directory '{cwd}' is outside the workspace."

        result = self.sandbox.execute(
            command=command,
            cwd=cwd,
            timeout=timeout,
        )

        parts: list[str] = []

        if not result.was_approved:
            return f"Command not approved: {result.stderr}"

        parts.append(f"Exit code: {result.returncode}")

        if result.stdout:
            parts.append(f"--- stdout ---\n{result.stdout}")

        if result.stderr:
            parts.append(f"--- stderr ---\n{result.stderr}")

        if result.timed_out:
            parts.append(f"Command timed out after {result.duration:.1f}s")

        parts.append(f"Duration: {result.duration:.2f}s")

        return "\n".join(parts)
