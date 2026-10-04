from pathlib import Path
from unittest.mock import patch

from nexus_agent.core.sandbox import Sandbox, SandboxConfig


def test_sandbox_windows_shell_injection():
    config = SandboxConfig()
    sandbox = Sandbox(workspace=Path("."), config=config)

    with patch("sys.platform", "win32"):
        # This command attempts to chain another command using &
        result = sandbox.execute("echo hello & calc")
        assert result.returncode == -1
        assert "Command contains unsafe Windows shell metacharacters" in result.stderr

        # This command uses valid input
        with patch("subprocess.run") as mock_run:
            # Setup valid return structure for the mock to avoid fallback failures
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "hello\n"
            mock_run.return_value.stderr = ""

            result = sandbox.execute("echo hello")
            assert mock_run.called
