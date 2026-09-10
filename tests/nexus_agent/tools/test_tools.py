"""Tests for the tool system."""

import pytest
from pathlib import Path

from nexus_agent.tools.base import Tool, ToolError, format_aci_output, summarize_search_results
from nexus_agent.tools.file_ops import ReadFileTool, WriteFileTool, SearchFilesTool, ListDirectoryTool
from nexus_agent.tools.shell import ShellTool
from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
from nexus_agent.tools.memory import MemoryTool
from nexus_agent.tools.todowrite import TodoWriteTool


class TestFormatACIOutput:
    def test_success_output(self):
        result = format_aci_output("content", success=True, tool_name="test")
        assert "[SUCCESS]" in result
        assert "content" in result

    def test_failure_output(self):
        result = format_aci_output("error", success=False, tool_name="test")
        assert "[FAILURE]" in result

    def test_empty_success(self):
        result = format_aci_output("", success=True, tool_name="test")
        assert "SUCCESS" in result
        assert "no output" in result.lower() or "executed successfully" in result.lower()

    def test_truncation(self):
        long_content = "x" * 5000
        result = format_aci_output(long_content, success=True)
        assert "truncated" in result.lower() or len(result) < 5000

    def test_with_metadata(self):
        result = format_aci_output(
            "content",
            success=True,
            metadata={"key": "value"},
        )
        assert "Metadata" in result or "key" in result


class TestSummarizeSearchResults:
    def test_empty_results(self):
        result = summarize_search_results([])
        assert "0 matches" in result or "no matches" in result.lower()

    def test_single_result(self):
        results = [{"path": "test.py", "line": 1, "content": "test"}]
        result = summarize_search_results(results)
        assert "test.py" in result

    def test_multiple_results(self):
        results = [
            {"path": "a.py", "line": 1, "content": "a"},
            {"path": "a.py", "line": 2, "content": "a"},
            {"path": "b.py", "line": 1, "content": "b"},
        ]
        result = summarize_search_results(results)
        assert "a.py" in result
        assert "b.py" in result


class TestToolBase:
    def test_tool_error(self):
        with pytest.raises(ToolError):
            raise ToolError("test error")


class TestReadFileTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return ReadFileTool(workspace=tmp_path)

    def test_read_file(self, tool, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\nprint('world')")
        result = tool.execute(path="test.py")
        assert "print" in result

    def test_read_nonexistent(self, tool):
        result = tool.execute(path="nonexistent.py")
        assert "Error" in result or "not found" in result.lower()

    def test_read_with_line_range(self, tool, tmp_path):
        test_file = tmp_path / "lines.txt"
        test_file.write_text("line1\nline2\nline3\nline4\nline5")
        result = tool.execute(path="lines.txt", start_line=2, end_line=4)
        assert "line2" in result
        assert "line4" in result

    def test_permission_level(self, tool):
        assert tool.permission_level == "read-only"


class TestWriteFileTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return WriteFileTool(workspace=tmp_path)

    def test_write_file(self, tool, tmp_path):
        result = tool.execute(path="new_file.py", content="print('hello')")
        assert "success" in result.lower() or "wrote" in result.lower()
        assert (tmp_path / "new_file.py").exists()

    def test_write_creates_dirs(self, tool, tmp_path):
        result = tool.execute(path="subdir/deep/file.py", content="test")
        assert (tmp_path / "subdir" / "deep" / "file.py").exists()

    def test_permission_level(self, tool):
        assert tool.permission_level == "read-write"

    def test_blocks_git_dir(self, tool):
        result = tool.execute(path=".git/hooks/test", content="malicious")
        assert "Error" in result


class TestSearchFilesTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return SearchFilesTool(workspace=tmp_path)

    def test_search(self, tool, tmp_path):
        (tmp_path / "test.py").write_text("def hello():\n    pass")
        result = tool.execute(pattern="def hello")
        assert "hello" in result

    def test_search_no_match(self, tool, tmp_path):
        (tmp_path / "test.py").write_text("pass")
        result = tool.execute(pattern="nonexistent_pattern_xyz")
        assert "No matches" in result or "no matches" in result.lower()

    def test_invalid_regex(self, tool):
        result = tool.execute(pattern="[invalid")
        assert "Error" in result


class TestListDirectoryTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return ListDirectoryTool(workspace=tmp_path)

    def test_list_dir(self, tool, tmp_path):
        (tmp_path / "file1.py").write_text("x")
        (tmp_path / "file2.py").write_text("y")
        result = tool.execute()
        assert "file1.py" in result
        assert "file2.py" in result

    def test_list_empty_dir(self, tool):
        result = tool.execute()
        assert "Empty" in result or "empty" in result.lower()


class TestShellTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return ShellTool(workspace=tmp_path)

    def test_execute_command(self, tool):
        result = tool.execute(command="echo hello")
        assert "hello" in result

    def test_permission_level(self, tool):
        assert tool.permission_level == "read-write"

    def test_exit_code(self, tool):
        # ShellTool in ASK mode needs approval, so test with a safe command
        result = tool.execute(command="echo test")
        assert "test" in result or "approved" in result.lower()


class TestCodeEditTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return CodeEditTool(workspace=tmp_path)

    def test_edit_file(self, tool, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("def old():\n    pass\n")
        result = tool.execute(
            path="test.py",
            old_content="def old():",
            new_content="def new():",
        )
        assert "edited" in result.lower() or "success" in result.lower()

    def test_edit_nonexistent(self, tool):
        result = tool.execute(
            path="nonexistent.py",
            old_content="x",
            new_content="y",
        )
        assert "Error" in result

    def test_edit_not_found(self, tool, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        result = tool.execute(
            path="test.py",
            old_content="nonexistent content",
            new_content="replacement",
        )
        assert "Error" in result or "not found" in result.lower()

    def test_permission_level(self, tool):
        assert tool.permission_level == "read-write"


class TestInsertLinesTool:
    @pytest.fixture
    def tool(self, tmp_path):
        return InsertLinesTool(workspace=tmp_path)

    def test_insert_lines(self, tool, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline3\n")
        result = tool.execute(
            path="test.py",
            line_number=2,
            content="line2\n",
        )
        content = test_file.read_text()
        assert "line2" in content

    def test_permission_level(self, tool):
        assert tool.permission_level == "read-write"


class TestTodoWriteTool:
    def test_create_todo(self):
        tool = TodoWriteTool()
        result = tool.execute(action="add", content="Test todo item")
        assert "success" in result.lower() or "added" in result.lower()

    def test_permission_level(self):
        tool = TodoWriteTool()
        assert tool.permission_level == "read-write"


class TestMemoryTool:
    def test_tool_creation(self):
        tool = MemoryTool()
        assert tool.name == "memory"
        assert tool.permission_level == "read-write"
