"""
Git Operations Tool — Git status, diff, commit, branch operations.

Includes state-of-the-art developer tooling:
- Smart Git conventional commits generation from diff
- Autocreated PR reviews, titles, and body summaries
- CI Pipeline log failure parser
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from nexus_agent.llm.base import Message, Role
from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)

MAX_OUTPUT_BYTES = 100 * 1024

# Whitelist of allowed git subcommands
ALLOWED_SUBCOMMANDS = {
    "status", "log", "diff", "branch", "show", "remote", "tag",
    "describe", "add", "commit", "push", "pull", "merge", "checkout",
    "reset", "stash", "init", "clone", "fetch", "rebase", "cherry-pick",
    "revert", "rm", "mv", "config", "help", "version",
}

_ARG_PATTERN = re.compile(r'^[a-zA-Z0-9./\-_=~^]+$')


class GitTool(Tool):
    """Execute git operations on the workspace repository."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()
        self._git_path: str = shutil.which("git") or "git"

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return (
            "Execute git operations: status, diff, log, branch, add, commit, etc. "
            "Provide the git subcommand and arguments."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "subcommand": {
                "type": "string",
                "description": "Git subcommand (e.g., 'status', 'diff', 'log', 'add', 'commit')",
            },
            "args": {
                "type": "string",
                "description": "Additional arguments for the git command",
                "required": False,
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["subcommand"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    def execute(self, subcommand: str, args: str = "", **kwargs: Any) -> str:
        # Whitelist subcommands to prevent argument injection
        if subcommand not in ALLOWED_SUBCOMMANDS:
            return f"Error: Git subcommand '{subcommand}' is not in the allowed list."

        # Validate each arg — alphanumeric + ./ -_ = ~ ^ only, max 100 chars
        if args:
            try:
                parsed_args = shlex.split(args)
            except ValueError as e:
                return f"Error: Invalid git arguments: {e}"
            for i, token in enumerate(parsed_args):
                if len(token) > 100:
                    return f"Error: Argument {i+1} exceeds maximum length of 100 characters."
                if not _ARG_PATTERN.match(token):
                    return (
                        f"Error: Argument {i+1} contains disallowed characters. "
                        f"Only alphanumeric, ., /, -, and _ are allowed. Got: '{token[:50]}...'"
                    )

        cmd = [self._git_path, subcommand]
        if args:
            cmd += parsed_args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.workspace),
                timeout=30,
                shell=False,
            )

            if len(result.stdout) > MAX_OUTPUT_BYTES:
                result.stdout = result.stdout[:MAX_OUTPUT_BYTES] + "\n... [truncated]"

            output_parts: list[str] = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"stderr: {result.stderr}")
            if result.returncode != 0:
                output_parts.append(f"Exit code: {result.returncode}")

            return "\n".join(output_parts) or "No output"

        except subprocess.TimeoutExpired:
            return "Error: git command timed out"
        except FileNotFoundError:
            return "Error: git is not installed or not in PATH"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"Error: {e}"


class SmartCommitTool(Tool):
    """Generate professional, contextual conventional commit messages from git diff."""

    def __init__(self, workspace: Path | None = None, provider: Any | None = None):
        self.workspace = workspace or Path.cwd()
        self.provider = provider

    @property
    def name(self) -> str:
        return "smart_commit"

    @property
    def description(self) -> str:
        return "Auto-generates a conventional commit message from currently staged changes."

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    @property
    def required_params(self) -> list[str]:
        return []

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, **kwargs: Any) -> str:
        # Check staged changes
        try:
            diff_staged = subprocess.run(
                ["git", "diff", "--staged"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15
            )
            diff_text = diff_staged.stdout.strip()
            if not diff_text:
                # Try tracking unstaged changes as a fallback
                diff_unstaged = subprocess.run(
                    ["git", "diff"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                diff_text = diff_unstaged.stdout.strip()
                if not diff_text:
                    return "No modifications or staged changes detected to commit."

            if self.provider:
                # LLM based generation
                system = (
                    "You are a git expert. Analyze the provided git diff and output a single, perfect conventional "
                    "commit message. Use conventional commits formatting (e.g. feat: add task graph module, "
                    "fix: resolve context timeout issue, docs: update readme). Do NOT add extra explanations, "
                    "backticks, or code blocks. Just output the raw commit message."
                )
                user = f"Git Diff:\n{diff_text[:3000]}"
                res = self.provider.chat_completion([
                    Message(role=Role.SYSTEM, content=system),
                    Message(role=Role.USER, content=user)
                ])
                return (res.content or "").strip()
            else:
                # Heuristic fallback
                files_changed = []
                for line in diff_text.splitlines():
                    if line.startswith("+++ b/"):
                        files_changed.append(line.replace("+++ b/", ""))

                summary = f"fix: update code in {', '.join(files_changed[:2])}"
                if any("test" in f for f in files_changed):
                    summary = f"test: update test cases in {', '.join(files_changed[:2])}"
                elif any("readme" in f.lower() or "doc" in f.lower() for f in files_changed):
                    summary = f"docs: update documentation for {', '.join(files_changed[:2])}"

                return f"{summary}\n\nAutomated commit message generated via local git heuristic."

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"Error analyzing git diff: {e}"


class PRGeneratorTool(Tool):
    """Generates Pull Request titles and descriptions from the commit history of a branch."""

    def __init__(self, workspace: Path | None = None, provider: Any | None = None):
        self.workspace = workspace or Path.cwd()
        self.provider = provider

    @property
    def name(self) -> str:
        return "pr_generator"

    @property
    def description(self) -> str:
        return "Auto-generates a Pull Request title and technical summary describing branch changes."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "base_branch": {
                "type": "string",
                "description": "Base branch to compare with (default: 'main')",
                "required": False,
            }
        }

    @property
    def required_params(self) -> list[str]:
        return []

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, base_branch: str = "main", **kwargs: Any) -> str:
        try:
            # 1. Get commit logs
            commits_res = subprocess.run(
                ["git", "log", f"{base_branch}..HEAD", "--oneline"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15
            )
            commits = commits_res.stdout.strip()

            # 2. Get high-level diff statistics
            diff_stat = subprocess.run(
                ["git", "diff", f"{base_branch}..HEAD", "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15
            )
            stats = diff_stat.stdout.strip()

            if not commits and not stats:
                return "No changes found compared to base branch."

            if self.provider:
                system = (
                    "You are a principal engineer. Create a compelling, professional Pull Request title and description "
                    "based on the provided commit messages and change stats. Format the description in Markdown with:\n"
                    "- **Overview**: Summary of changes\n"
                    "- **Key Features / Fixes**: Bullet points explaining modifications\n"
                    "- **Dependencies**: List of modified key files"
                )
                user = f"Commits:\n{commits}\n\nDiff Stats:\n{stats}"
                res = self.provider.chat_completion([
                    Message(role=Role.SYSTEM, content=system),
                    Message(role=Role.USER, content=user)
                ])
                return (res.content or "").strip()
            else:
                # Heuristic markdown
                lines = [
                    "# PR Summary: Branch modifications",
                    "",
                    "## Commit Log:",
                    commits or "*No commits (direct index changes)*",
                    "",
                    "## Stat Summary:",
                    stats
                ]
                return "\n".join(lines)

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError) as e:
            return f"Error compiling branch details: {e}"


class CIAnalyzerTool(Tool):
    """Analyzes CI Pipeline execution logs and diagnoses exact failures."""

    def __init__(self, provider: Any | None = None):
        self.provider = provider

    @property
    def name(self) -> str:
        return "ci_analyzer"

    @property
    def description(self) -> str:
        return "Analyzes a raw CI log, extracts failing steps, and diagnoses causes."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "log_text": {
                "type": "string",
                "description": "The raw log output text from the CI failure",
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["log_text"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, log_text: str, **kwargs: Any) -> str:
        if not log_text or not log_text.strip():
            return "Please provide non-empty log output to analyze."

        # Extract only failing blocks to avoid token bloat
        lines = log_text.splitlines()
        failures = []
        capture = False
        captured_lines = 0

        # Heuristic extraction of failing lines
        for line in lines:
            if any(k in line.lower() for k in ["fail", "error", "exception", "traceback", "panic", "fatal"]):
                capture = True
                captured_lines = 0

            if capture:
                failures.append(line)
                captured_lines += 1
                if captured_lines > 20:  # Capture 20 lines around each error indicator
                    capture = False

        excerpt = "\n".join(failures[:200]) if failures else log_text[:2000]

        if self.provider:
            system = (
                "You are an expert DevOps engineer and debugger. Read the provided CI log output block. "
                "Diagnose exactly why the CI failed, highlight the root error file/line/context, and provide "
                "the exact corrective actions to fix it."
            )
            res = self.provider.chat_completion([
                Message(role=Role.SYSTEM, content=system),
                Message(role=Role.USER, content=excerpt)
            ])
            return (res.content or "").strip()
        else:
            # Rule based highlight
            parsed = []
            for line in excerpt.splitlines():
                if "error" in line.lower() or "fail" in line.lower():
                    parsed.append(f"🔴 {line}")
                else:
                    parsed.append(line)
            return "### CI Failure Diagnostic Report (Heuristic)\n\n" + "\n".join(parsed[:50])
