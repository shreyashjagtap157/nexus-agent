"""
Command Execution Sandbox.

Provides configurable isolation for shell command execution.
Supports three modes inspired by codex and claude-code:
- Suggest: Show command but don't execute (safest)
- Ask: Prompt user for approval before executing
- Auto: Execute with permission rules (most convenient)
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


dangerous_indicators: tuple[str, ...] = (
    r"\brm\s+-rf\b", r"\bsudo\b", r"\bformat\b",
    r"\bmkfs\b", r"\bdd\s+if=", r"\bchmod\s+777\b",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
    r"\binit\s+0\b", r"(:\(\)\s*\{)", r"\bmv\s+/", r"\bcp\s+/",
)


class SandboxMode(str, Enum):
    """Sandbox execution modes."""
    SUGGEST = "suggest"  # Show command, don't execute
    ASK = "ask"          # Ask user before executing
    AUTO = "auto"        # Execute with rule-based permissions


class CommandRisk(str, Enum):
    """Risk level of a command."""
    SAFE = "safe"           # Read-only commands (ls, cat, git status)
    MODERATE = "moderate"   # Write commands (git commit, pip install)
    DANGEROUS = "dangerous" # Destructive commands (rm -rf, format)
    BLOCKED = "blocked"     # Never allow (sudo rm -rf /)


@dataclass
class CommandResult:
    """Result of a command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    was_approved: bool = True
    risk_level: CommandRisk = CommandRisk.SAFE
    timed_out: bool = False


@dataclass
class SandboxConfig:
    """Configuration for the execution sandbox."""
    mode: SandboxMode = SandboxMode.ASK
    timeout: int = 60  # seconds
    max_output_size: int = 100_000  # characters

    # Regex patterns for command classification
    allowed_patterns: list[str] = field(default_factory=lambda: [
        r"^ls\b", r"^dir\b", r"^cat\b", r"^head\b", r"^tail\b",
        r"^grep\b", r"^find\b", r"^wc\b", r"^echo\b",
        r"^git\s+(status|log|diff|branch|show|remote|tag|describe)\b",
        r"^node\s+--version\b",
        r"^type\b", r"^more\b", r"^where\b", r"^which\b",
        r"^pwd\b",
        r"^stat\b", r"^md5sum\b", r"^sha256sum\b",
        r"^sort\b", r"^uniq\b", r"^cut\b", r"^awk\b",
    ])

    denied_patterns: list[str] = field(default_factory=lambda: [
        r"^rm\s+-rf\s+/", r"^sudo\b", r"^format\b",
        r"^mkfs\b", r"^dd\s+if=", r"^chmod\s+777\b",
        r">\s*/dev/sd", r"^shutdown\b", r"^reboot\b",
        r"^:(){ :\|:& };:",  # Fork bomb
        r"^python\s+-c\b", r"^python\s+-m\b",  # Arbitrary code execution via -c/-m
        r"^node\s+-e\b", r"^node\s+-p\b", r"^node\s+-r\b",  # Node arbitrary code
        r"^bash\s+-c\b", r"^sh\s+-c\b", r"^zsh\s+-c\b",  # Shell arbitrary code
        r"^eval\b", r"^exec\b",  # Shell builtin code execution
        r"^curl\s+.*\|", r"^wget\s+.*\|",  # Pipe download to shell
    ])

    # Workspace boundary is always enforced in _resolve_safe_path


class Sandbox:
    """Sandboxed command execution environment.

    Provides safe command execution with permission checks,
    output limits, and timeout handling.
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        workspace: Path | None = None,
        approval_callback: Callable[[str, CommandRisk], bool] | None = None,
    ):
        """Initialize sandbox.

        Args:
            config: Sandbox configuration.
            workspace: Working directory.
            approval_callback: Function(command, risk) → bool for approval.
        """
        self.config = config or SandboxConfig()
        self.workspace = workspace or Path.cwd()
        self.approval_callback = approval_callback
        self._history: list[CommandResult] = []

    def _split_commands(self, command: str) -> list[str]:
        """Split a shell command into individual subcommands.
        
        Handles shell operators: &&, ||, ;, |, \n
        Each subcommand is trimmed and checked independently.
        """
        segments = re.split(r'\s*(?:&&|\|\||;|\||\n)\s*', command)
        return [s.strip() for s in segments if s.strip()]

    def classify_risk(self, command: str) -> CommandRisk:
        """Classify the risk level of a command.

        Splits chained/piped commands (; && || |) and classifies
        each segment independently, returning the worst risk found.

        Args:
            command: The shell command to classify.

        Returns:
            CommandRisk level.
        """
        cmd_stripped = command.strip()
        segments = self._split_commands(cmd_stripped)
        if not segments:
            return CommandRisk.SAFE

        # Check denied patterns on each segment
        for seg in segments:
            for pattern in self.config.denied_patterns:
                try:
                    if re.search(pattern, seg, re.IGNORECASE):
                        return CommandRisk.BLOCKED
                except re.error as exc:
                    logger.warning(f"Invalid regex in denied_patterns: {pattern!r} ({exc})")

        # Check allowed patterns — every segment must be independently safe
        all_safe = True
        for seg in segments:
            seg_safe = False
            for pattern in self.config.allowed_patterns:
                try:
                    if re.match(pattern, seg, re.IGNORECASE):
                        seg_safe = True
                        break
                except re.error as exc:
                    logger.warning(f"Invalid regex in allowed_patterns: {pattern!r} ({exc})")
            if not seg_safe:
                all_safe = False
                break

        if all_safe:
            return CommandRisk.SAFE

        # Heuristic classification on each segment
        for seg in segments:
            for indicator in dangerous_indicators:
                try:
                    if re.search(indicator, seg, re.IGNORECASE):
                        return CommandRisk.DANGEROUS
                except re.error as exc:
                    logger.warning(f"Invalid regex in dangerous_indicators: {indicator!r} ({exc})")

        write_indicators = [
            "mv ", "cp ", "mkdir", "touch", "echo >",
            "git commit", "git push", "git merge",
            "pip install", "npm install", "npm run",
            "python ", "node ",
        ]
        for seg in segments:
            seg_lower = seg.lower()
            for indicator in write_indicators:
                if indicator in seg_lower:
                    return CommandRisk.MODERATE

        return CommandRisk.MODERATE  # Unknown commands are moderate risk

    def can_execute(self, command: str) -> tuple[bool, str]:
        """Check if a command can be executed.

        Returns:
            Tuple of (can_execute, reason).
        """
        risk = self.classify_risk(command)

        if risk == CommandRisk.BLOCKED:
            return False, "Command blocked: matches denied pattern"

        if self.config.mode == SandboxMode.SUGGEST:
            return False, "Sandbox in suggest mode — command not executed"

        if self.config.mode == SandboxMode.ASK:
            if risk == CommandRisk.SAFE:
                return True, "Safe command — auto-approved"
            # Need user approval
            if self.approval_callback:
                approved = self.approval_callback(command, risk)
                return approved, "User approved" if approved else "User denied"
            return False, "Awaiting user approval"

        if self.config.mode == SandboxMode.AUTO:
            if risk == CommandRisk.DANGEROUS:
                if self.approval_callback:
                    approved = self.approval_callback(command, risk)
                    return approved, "User approved" if approved else "User denied"
                return False, "Dangerous command requires explicit approval"
            return True, "Auto-approved"

        return False, "Unknown sandbox mode"

    def _resolve_safe_path(self, path: Path) -> Path:
        """Resolve a path safely to prevent TOCTOU/symlink-race attacks.

        On Unix, uses os.open + os.fstat to verify the device/inode
        haven't changed between resolution and use. On all platforms,
        enforces workspace boundary.
        """
        try:
            resolved = path.expanduser().resolve()
            if sys.platform != "win32":
                fd = os.open(str(resolved), os.O_RDONLY | os.O_NONBLOCK)
                try:
                    st = os.fstat(fd)
                    resolved_st = os.stat(str(resolved))
                    if st.st_dev != resolved_st.st_dev or st.st_ino != resolved_st.st_ino:
                        logger.warning(f"TOCTOU symlink race detected for path: {path}")
                        return self.workspace
                finally:
                    os.close(fd)
            elif not resolved.is_dir():
                logger.warning(f"Resolved path is not a directory: {resolved}")
                return self.workspace
            # Enforce workspace boundary on all platforms
            workspace_resolved = self.workspace.resolve()
            if not str(resolved).startswith(str(workspace_resolved) + os.sep) and resolved != workspace_resolved:
                logger.warning(f"Path {resolved} is outside workspace boundary {workspace_resolved}")
                return self.workspace
            return resolved
        except (OSError, ValueError) as e:
            logger.warning(f"Path resolution failed for {path}: {e}")
            return self.workspace

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Execute a shell command within the sandbox.

        Args:
            command: Shell command to execute.
            cwd: Working directory (defaults to workspace).
            timeout: Timeout in seconds.
            env: Additional environment variables.

        Returns:
            CommandResult with output and metadata.
        """
        risk = self.classify_risk(command)
        can_run, reason = self.can_execute(command)

        if not can_run:
            result = CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Execution denied: {reason}",
                duration=0.0,
                was_approved=False,
                risk_level=risk,
            )
            self._history.append(result)
            return result

        # Determine working directory (TOCTOU-safe resolution)
        work_dir = self._resolve_safe_path(Path(cwd)) if cwd else self.workspace

        # Build environment
        exec_env = os.environ.copy()
        if env:
            # Sanitize additional env variables to prevent PATH hijacking or execution override vectors
            for k, v in dict(env).items():
                k_clean = str(k).strip()
                v_clean = str(v).strip()
                if k_clean.upper() in ("PATH", "LD_PRELOAD", "PYTHONPATH", "NODE_PATH"):
                    logger.warning(f"Blocked override of critical environment variable: {k_clean}")
                    continue
                exec_env[k_clean] = v_clean

        # Execute
        effective_timeout = timeout or self.config.timeout
        start_time = time.time()

        try:
            # Parse command to avoid shell injection - use list form
            try:
                parsed_args = shlex.split(command)
            except ValueError:
                parsed_args = None

            if parsed_args:
                # Use direct execution on both Unix and Windows when parsing succeeds
                if sys.platform == "win32":
                    # On Windows, use cmd.exe /c with parsed args (no shell interpretation)
                    cmd_args = ["cmd.exe", "/c"] + parsed_args
                    proc = subprocess.run(
                        cmd_args,
                        capture_output=True,
                        text=True,
                        cwd=str(work_dir),
                        env=exec_env,
                        timeout=effective_timeout,
                    )
                else:
                    proc = subprocess.run(
                        parsed_args,
                        capture_output=True,
                        text=True,
                        cwd=str(work_dir),
                        env=exec_env,
                        timeout=effective_timeout,
                    )
            elif sys.platform == "win32":
                # Windows fallback: shlex.split failed, use PowerShell with proper escaping
                escaped_cmd = subprocess.list2cmdline([command])
                shell_cmd = ["powershell", "-NoProfile", "-Command", escaped_cmd]
                proc = subprocess.run(
                    shell_cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(work_dir),
                    env=exec_env,
                    timeout=effective_timeout,
                )
            else:
                # Unix fallback: parse failed, use sh -c (best effort)
                proc = subprocess.run(
                    ["/bin/sh", "-c", command],
                    capture_output=True,
                    text=True,
                    cwd=str(work_dir),
                    env=exec_env,
                    timeout=effective_timeout,
                )

            duration = time.time() - start_time

            # Truncate output if too large
            stdout = proc.stdout
            stderr = proc.stderr

            if len(stdout) > self.config.max_output_size:
                stdout = stdout[:self.config.max_output_size] + "\n[... output truncated ...]"

            if len(stderr) > self.config.max_output_size:
                stderr = stderr[:self.config.max_output_size] + "\n[... output truncated ...]"

            result = CommandResult(
                command=command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                was_approved=True,
                risk_level=risk,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            result = CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout}s",
                duration=duration,
                was_approved=True,
                risk_level=risk,
                timed_out=True,
            )

        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            duration = time.time() - start_time
            result = CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Execution error: {e}",
                duration=duration,
                was_approved=True,
                risk_level=risk,
            )

        self._history.append(result)
        logger.info(
            f"Command executed: {command[:80]}... "
            f"(rc={result.returncode}, {duration:.1f}s, risk={risk.value})"
        )

        return result

    def get_history(self) -> list[CommandResult]:
        """Get command execution history."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear command history."""
        self._history.clear()
