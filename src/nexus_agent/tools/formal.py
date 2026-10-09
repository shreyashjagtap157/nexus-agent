"""Local formal-verification tool adapters.

The tool never invokes a shell. It selects from an explicit executable allow-list,
runs in the current workspace, enforces a wall-clock timeout and records enough
metadata for an agent/auditor to reproduce the check.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool


class FormalCheckTool(Tool):
    """Run an installed formal verifier against an explicitly named workspace file."""

    _ADAPTERS: dict[str, tuple[str, list[str]]] = {
        "z3": ("z3", ["z3", "{file}"]),
        "lean": ("lean", ["lean", "{file}"]),
        "lake": ("lake", ["lake", "env", "lean", "{file}"]),
        "rocq": ("rocq", ["rocq", "compile", "{file}"]),
        "coq": ("coqc", ["coqc", "{file}"]),
        "dafny": ("dafny", ["dafny", "verify", "{file}"]),
        "tlc": ("tlc", ["tlc", "-workers", "auto", "{file}"]),
        "apalache": ("apalache-mc", ["apalache-mc", "check", "{file}"]),
        "alloy": ("alloy", ["alloy", "{file}"]),
        "k": ("kompile", ["kompile", "{file}"]),
    }

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()

    @property
    def name(self) -> str:
        return "formal_check"

    @property
    def description(self) -> str:
        return (
            "Run an installed formal verifier (Z3, Lean, Rocq/Coq, Dafny, "
            "TLC/Apalache, Alloy or K Framework) against a workspace model. "
            "The tool is deterministic at the process level and returns the verifier "
            "exit status, stdout/stderr and executable availability."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "verifier": {
                "type": "string",
                "description": "z3, lean, lake, rocq, coq, dafny, tlc, apalache, alloy or k",
            },
            "file": {
                "type": "string",
                "description": "Workspace-relative model/source file to verify.",
            },
            "timeout": {
                "type": "integer",
                "description": "Wall-clock timeout in seconds, 1-3600.",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    @property
    def timeout(self) -> int:
        return 3600

    def execute(
        self, verifier: str, file: str, timeout: int = 300, **kwargs: Any
    ) -> dict[str, Any]:
        normalized = verifier.strip().lower()
        adapter = self._ADAPTERS.get(normalized)
        if adapter is None:
            return {"ok": False, "verifier": normalized, "error": "Unsupported verifier."}

        try:
            target = Tool.resolve_workspace_path(self.workspace, file)
        except ValueError as exc:
            return {"ok": False, "verifier": normalized, "error": str(exc)}
        if not target.is_file():
            return {"ok": False, "verifier": normalized, "error": f"File not found: {file}"}

        executable, argv_template = adapter
        executable_path = shutil.which(executable)
        if executable_path is None:
            return {
                "ok": False,
                "verifier": normalized,
                "status": "unavailable",
                "error": f"Verifier executable {executable!r} is not installed or not on PATH.",
            }

        argv = [item.replace("{file}", str(target)) for item in argv_template]
        limit = max(1, min(int(timeout), 3600))
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                argv,
                cwd=str(self.workspace),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=limit,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "verifier": normalized,
                "status": "timeout",
                "timeout_seconds": limit,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "stdout": str(exc.stdout or "")[-20000:],
                "stderr": str(exc.stderr or "")[-20000:],
            }
        except OSError as exc:
            return {
                "ok": False,
                "verifier": normalized,
                "status": "execution_error",
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

        return {
            "ok": completed.returncode == 0,
            "verifier": normalized,
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
            "executable": executable_path,
            "file": str(target.relative_to(self.workspace)),
        }
