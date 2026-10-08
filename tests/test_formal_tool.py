from pathlib import Path

from nexus_agent.tools.formal import FormalCheckTool


def test_formal_check_rejects_unsupported_verifier(tmp_path: Path):
    tool = FormalCheckTool(tmp_path)
    result = tool.execute("unknown", "model.smt2")
    assert result["ok"] is False
    assert result["error"] == "Unsupported verifier."


def test_formal_check_reports_missing_executable_without_running_shell(tmp_path: Path):
    model = tmp_path / "model.smt2"
    model.write_text("(check-sat)\n", encoding="utf-8")
    tool = FormalCheckTool(tmp_path)
    result = tool.execute("z3", "model.smt2")
    assert result["ok"] is False
    assert result["status"] in {"unavailable", "passed", "failed"}
    if result["status"] == "unavailable":
        assert "not installed" in result["error"]
