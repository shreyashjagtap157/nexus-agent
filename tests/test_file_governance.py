from pathlib import Path

from nexus_agent.tools.file_ops import DeleteFileTool, MoveFileTool, WriteFileTool
from nexus_agent.tools.restore_file import RestoreFileTool


def test_file_mutations_are_reversible_and_journaled(tmp_path: Path):
    writer = WriteFileTool(tmp_path)
    assert "Successfully wrote" in writer.execute("demo.txt", "hello")
    deleter = DeleteFileTool(tmp_path)
    result = deleter.execute("demo.txt")
    assert "NexusAgent trash:" in result
    trash_name = result.rsplit("/", 1)[-1]
    restorer = RestoreFileTool(tmp_path)
    restored = restorer.execute("restore", trash_name, "demo-restored.txt")
    assert "Restored" in restored
    assert (tmp_path / "demo-restored.txt").read_text(encoding="utf-8") == "hello"


def test_move_file_records_a_safe_workspace_move(tmp_path: Path):
    WriteFileTool(tmp_path).execute("before.txt", "data")
    result = MoveFileTool(tmp_path).execute("before.txt", "after.txt")
    assert result == "Moved before.txt -> after.txt"
    assert not (tmp_path / "before.txt").exists()
    assert (tmp_path / "after.txt").read_text(encoding="utf-8") == "data"
