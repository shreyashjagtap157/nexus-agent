"""
Autonomous DevOps Pipeline — Local CI/CD static scanning, vulnerability audits, and test suites.

Enables the agent to create git checkpoints, auto-detect local test frameworks, run linters,
parse stack traces, scan for secrets, run dependency vulnerability audits, and self-heal test failures.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class SecretMatch:
    """A matched potential secret pattern in code."""
    file_path: str
    line_number: int
    matched_pattern: str
    pattern_name: str


@dataclass
class PipelineReport:
    """Consolidated execution report for the DevOps verification pipeline."""
    success: bool
    test_framework_detected: str | None
    tests_passed: bool
    test_output: str
    linters_passed: bool
    linter_output: str
    secrets_found: list[SecretMatch] = field(default_factory=list)
    vulnerabilities_found: list[str] = field(default_factory=list)
    traceback_analysis: str | None = None
    git_checkpoint_branch: str | None = None


class TestRunner:
    """Detects and runs test frameworks."""

    FRAMEWORK_INDICATORS = {
        "pytest": ["pytest.ini", "conftest.py", "tox.ini", "tests/conftest.py"],
        "npm-jest": ["jest.config.js", "jest.config.ts"],
        "cargo": ["Cargo.toml"],
        "go": ["go.mod"],
        "pytest-fallback": ["tests/"],
    }

    FRAMEWORK_COMMANDS = {
        "pytest": ["python", "-m", "pytest", "tests"],
        "unittest": ["python", "-m", "unittest", "discover", "-s", "tests"],
        "npm-jest": ["npm", "test"],
        "cargo": ["cargo", "test"],
        "go": ["go", "test", "./..."],
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def detect_framework(self) -> str | None:
        """Auto-detect test frameworks based on file indicators."""
        for fw, files in self.FRAMEWORK_INDICATORS.items():
            for f in files:
                if (self.workspace / f).exists():
                    if fw == "pytest-fallback":
                        if (self.workspace / "pyproject.toml").exists() or list((self.workspace / "tests").glob("**/*.py")):
                            return "pytest"
                    else:
                        return fw.replace("-fallback", "")

        if list(self.workspace.glob("*.py")) or list((self.workspace / "src").glob("**/*.py") if (self.workspace / "src").exists() else []):
            return "unittest"

        return None

    def run(self) -> tuple[bool, str]:
        """Execute the detected test suite."""
        framework = self.detect_framework()
        if not framework:
            return True, "No test framework detected. Skipping test execution."

        cmd = self.FRAMEWORK_COMMANDS.get(framework)
        if not cmd:
            return True, f"Unsupported test framework '{framework}'."

        try:
            logger.info(f"Executing test command: {' '.join(cmd)}")
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120
            )
            return res.returncode == 0, res.stdout
        except subprocess.TimeoutExpired as te:
            return False, f"Test suite timed out after 120 seconds. Output:\n{te.stdout or ''}"
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.warning(f"Test execution failed: {e}")
            return False, f"Failed to execute tests: {e}"


class LinterRunner:
    """Discovers and runs available linters."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def _command_exists(self, binary: str) -> bool:
        """Check if a command is available on PATH."""
        try:
            subprocess.run(
                ["where" if os.name == "nt" else "which", binary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def _run_single(self, cmd: list[str]) -> tuple[bool, str]:
        """Run a single linter command."""
        binary = cmd[0]
        if not self._command_exists(binary):
            return True, ""  # Skip silently

        try:
            logger.info(f"Running linter: {' '.join(cmd)}")
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30
            )
            output = f"--- Linter: {' '.join(cmd)} ---\n{res.stdout}"
            return res.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Linter '{binary}' timed out after 30s"
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.warning(f"Linter '{binary}' failed: {e}")
            return False, f"Linter '{binary}' failed to execute: {e}"

    def run_all(self) -> tuple[bool, str]:
        """Run all available linters sequentially."""
        linter_cmds = []
        if (self.workspace / "pyproject.toml").exists() or list(self.workspace.glob("*.py")):
            linter_cmds.append(["ruff", "check", "."])
            linter_cmds.append(["mypy", "."])
        if (self.workspace / "package.json").exists():
            linter_cmds.append(["npm", "run", "lint"])

        if not linter_cmds:
            return True, "No linters configured or available."

        passed = True
        outputs = []
        for cmd in linter_cmds:
            ok, out = self._run_single(cmd)
            if not ok:
                passed = False
            if out:
                outputs.append(out)

        return passed, "\n".join(outputs)


class SecretScanner:
    """Scans workspace files for potential secrets and credentials."""

    PATTERNS = {
        "Generic Password/Secret": r'(?:password|passwd|secret|passphrase|private_key|app_secret|client_secret)\s*[:=]\s*[\'"][a-zA-Z0-9_\-\.\/\+\=\~\!\@\#\$\%\^\&\*\(\)]+[\'"]',
        "Slack Token": r'xox[bapr]-[0-9]{12}-[a-zA-Z0-9]{24}',
        "GitHub Personal Access Token": r'ghp_[a-zA-Z0-9]{36}',
        "AWS API Key/Secret": r'(?:AKIA[0-9A-Z]{16}|[a-zA-Z0-9+/]{40})',
        "Google API Key": r'AIzaSy[a-zA-Z0-9\-_]{33}',
        "Database Connection URL": r'(?:mongodb|postgres|postgresql|mysql|redis|sqlite):\/\/[a-zA-Z0-9_]+:[a-zA-Z0-9_\-\~\!\@\#]+@[a-zA-Z0-9_\-\.]+:[0-9]+',
    }

    EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist", ".nexus-agent"}
    VALID_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".json", ".ini", ".conf", ".go", ".rs"}

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }

    def scan(self) -> list[SecretMatch]:
        """Recursively scan workspace files for secrets."""
        matches: list[SecretMatch] = []

        try:
            for root, dirs, files in os.walk(str(self.workspace)):
                dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix not in self.VALID_EXTENSIONS:
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        for line_idx, line in enumerate(content.splitlines(), 1):
                            if line.strip().startswith("#") or line.strip().startswith("//"):
                                continue
                            for name, compiled_re in self._compiled_patterns.items():
                                if compiled_re.search(line):
                                    matches.append(SecretMatch(
                                        file_path=str(file_path.relative_to(self.workspace)),
                                        line_number=line_idx,
                                        matched_pattern=line.strip()[:100],
                                        pattern_name=name
                                    ))
                    except (OSError, UnicodeDecodeError, re.error) as e:
                        logger.warning(f"Failed to scan {file_path}: {e}")
        except (OSError, ValueError) as e:
            logger.error(f"Secrets scan encountered failure: {e}")

        return matches


class GitCheckpointer:
    """Manages git checkpoint branches for safe operations."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def get_current_branch(self) -> str | None:
        """Get the current git branch name."""
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return res.stdout.strip() if res.returncode == 0 else None
        except (OSError, subprocess.CalledProcessError, subprocess.SubprocessError) as e:
            logger.warning(f"Failed to get current branch: {e}")
            return None

    def create_safety_branch(self) -> str | None:
        """Create a temporary git branch checkpoint, stashing changes first."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if res.returncode != 0:
                return None

            # Stash any uncommitted changes
            subprocess.run(
                ["git", "stash", "push", "-m", "nexus-safety-stash"],
                cwd=str(self.workspace),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            import uuid
            branch_name = f"nexus-safety-{int(os.path.getmtime(str(self.workspace)))}-{uuid.uuid4().hex[:6]}"
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=str(self.workspace),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return branch_name
        except (OSError, ValueError, subprocess.CalledProcessError, subprocess.SubprocessError) as e:
            logger.warning(f"Failed to create safety branch: {e}")
            return None

    def restore_branch(self, branch_name: str) -> None:
        """Restore to a specified branch, discarding any uncommitted changes."""
        try:
            subprocess.run(
                ["git", "checkout", "--force", branch_name],
                cwd=str(self.workspace),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Pop the stash if one was created
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(self.workspace),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.SubprocessError) as e:
            logger.warning(f"Failed to restore branch '{branch_name}': {e}")


class VulnerabilityScanner:
    """Scans dependencies for known vulnerabilities."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def scan_python(self) -> list[str]:
        """Run pip-audit for Python vulnerabilities."""
        vulns: List[str] = []
        if not ((self.workspace / "requirements.txt").exists() or (self.workspace / "pyproject.toml").exists()):
            return vulns

        try:
            res = subprocess.run(
                ["pip-audit", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode != 0:
                logger.info("pip-audit not installed, skipping Python vulnerability scan")
                return vulns

            audit = subprocess.run(
                ["pip-audit", "-r", "requirements.txt"] if (self.workspace / "requirements.txt").exists() else ["pip-audit"],
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if audit.returncode != 0:
                vulns.append("--- pip-audit warnings ---")
                vulns.append(audit.stdout or audit.stderr)
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            logger.warning(f"pip-audit scan failed: {e}")
        return vulns

    def scan_node(self) -> list[str]:
        """Run npm audit for Node vulnerabilities."""
        vulns: List[str] = []
        if not (self.workspace / "package.json").exists():
            return vulns

        try:
            audit = subprocess.run(
                ["npm", "audit", "--audit-level=high"],
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if audit.returncode != 0:
                vulns.append("--- npm audit warnings ---")
                vulns.append(audit.stdout)
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            logger.warning(f"npm audit failed: {e}")
        return vulns

    def scan_all(self) -> list[str]:
        """Run all available vulnerability scanners."""
        return self.scan_python() + self.scan_node()


def parse_traceback(stderr: str) -> str | None:
    """Extract line number, file name, and error message from multi-language tracebacks."""
    py_match = re.findall(r'File "([^"]+)", line (\d+), in [^\n]+\n\s*([^\n]+)', stderr)
    if py_match:
        lines = ["### Python Traceback Analysis:"]
        for file, line, error in py_match[-3:]:
            lines.append(f"- File: `{file}` (Line: {line})")
            lines.append(f"  Error Detail: `{error.strip()}`")
        return "\n".join(lines)

    js_match = re.findall(r'at [^(]*\(([^:]+):(\d+):(\d+)\)', stderr)
    if js_match:
        lines = ["### JavaScript Stacktrace Analysis:"]
        for file, line, col in js_match[:3]:
            lines.append(f"- File: `{file}` (Line: {line}, Column: {col})")
        return "\n".join(lines)

    go_match = re.findall(r'([^ \t\n]+):(\d+) \+0x[0-9a-fA-F]+', stderr)
    if go_match:
        lines = ["### Go Panic Analysis:"]
        for file, line in go_match[:3]:
            lines.append(f"- File: `{file}` (Line: {line})")
        return "\n".join(lines)

    return None


class VerificationPipeline:
    """Autonomous DevOps static linter, secret scanner, and test verification suite."""

    def __init__(self, workspace: Path | None = None):
        """Initialize the verification pipeline.

        Args:
            workspace: The workspace root directory.
        """
        self.workspace = workspace or Path.cwd()
        self.test_runner = TestRunner(self.workspace)
        self.linter_runner = LinterRunner(self.workspace)
        self.secret_scanner = SecretScanner(self.workspace)
        self.vuln_scanner = VulnerabilityScanner(self.workspace)
        self.git_checkpointer = GitCheckpointer(self.workspace)

    def scan_vulnerabilities(self) -> list[str]:
        """Delegate to VulnerabilityScanner."""
        return self.vuln_scanner.scan_all()

    def run_full_pipeline(self) -> PipelineReport:
        """Run all suite checkpoints: snapshot -> static scans -> linters -> test framework."""
        original_branch = self.git_checkpointer.get_current_branch()

        checkpoint = None
        try:
            checkpoint = self.git_checkpointer.create_safety_branch()

            fw = self.test_runner.detect_framework()

            # Run tests and linters in parallel
            tests_passed, test_output = True, "No test output"
            linters_passed, linter_output = True, "No linter output"
            with ThreadPoolExecutor(max_workers=2) as executor:
                test_future = executor.submit(self.test_runner.run)
                lint_future = executor.submit(self.linter_runner.run_all)
                for future in as_completed([test_future, lint_future]):
                    try:
                        ok, out = future.result()
                        if future == test_future:
                            tests_passed, test_output = ok, out
                        else:
                            linters_passed, linter_output = ok, out
                    except (OSError, ValueError, subprocess.CalledProcessError, TimeoutError) as e:
                        logger.error(f"Parallel pipeline task failed: {e}")

            secrets = self.secret_scanner.scan()
            vulns = self.vuln_scanner.scan_all()

            trace = None
            if not tests_passed:
                trace = parse_traceback(test_output)

            success = tests_passed and linters_passed and len(secrets) == 0

            return PipelineReport(
                success=success,
                test_framework_detected=fw,
                tests_passed=tests_passed,
                test_output=test_output,
                linters_passed=linters_passed,
                linter_output=linter_output,
                secrets_found=secrets,
                vulnerabilities_found=vulns,
                traceback_analysis=trace,
                git_checkpoint_branch=checkpoint
            )
        finally:
            if original_branch and checkpoint:
                self.git_checkpointer.restore_branch(original_branch)
