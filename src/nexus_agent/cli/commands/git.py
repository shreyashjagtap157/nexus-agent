"""Git slash commands — /diff, /branch, /commit, /pr."""

from __future__ import annotations

import subprocess

from rich.syntax import Syntax

from nexus_agent.cli.commands._base import BaseCommands


class GitCommands(BaseCommands):
    """Mixin providing git-related slash command handlers."""


    def _cmd_diff(self, args: str):
        target = args or "HEAD"
        try:
            result = subprocess.run(
                ["git", "diff", target],
                cwd=str(self.workspace), capture_output=True, text=True, timeout=15,
            )
            output = result.stdout or result.stderr or "(no diff)"
            if len(output) > 3000:
                output = output[:3000] + f"\n  ... (truncated, {len(output)} total chars)"
            self.console.print(Syntax(output, "diff", theme="monokai", word_wrap=True))
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Diff failed: {e}")


    def _cmd_branch(self, args: str):
        try:
            if args:
                cmd = ["git", "checkout", args]
            else:
                result = subprocess.run(["git", "branch"], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
                self.console.print(f"  [dim]{result.stdout.strip()}[/dim]")
                return
            subprocess.run(cmd, cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
            self.r.system_message(f"Switched to branch: {args}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Branch: {e}")


    def _cmd_commit(self, args: str):
        if not self._agent:
            self.r.system_message("No agent.")
            return
        from nexus_agent.tools.git_ops import SmartCommitTool
        self.r.show_spinner("Generating commit message")
        try:
            tool = SmartCommitTool(workspace=self.workspace, provider=self._agent.provider)
            msg = tool.execute()
            self.r.hide_spinner()
            self.console.print(f"\n  [dim]{msg}[/dim]\n")
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.r.hide_spinner()
            self.r.error(f"Commit: {e}")


    def _cmd_pr(self, args: str):
        from nexus_agent.tools.git_ops import PRReviewTool
        self.r.show_spinner("Generating PR summary")
        try:
            pr_tool = PRReviewTool(workspace=self.workspace, provider=self._agent.provider if self._agent else None)
            summary = pr_tool.execute()
            self.r.hide_spinner()
            self.r.assistant_message(summary)
        except (ValueError, RuntimeError) as e:
            self.r.hide_spinner()
            self.r.error(f"PR: {e}")
