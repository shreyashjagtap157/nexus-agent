"""Unit tests to verify clean imports of all package submodules."""

import unittest

class TestPackageImports(unittest.TestCase):
    """Test case for package module imports."""

    def test_core_imports(self) -> None:
        """Verify core imports."""
        from nexus_agent.core import AgentLoop, AgentMode, AgentState, AgentEvent, ToolResult
        from nexus_agent.core import Planner, Executor, Orchestrator
        self.assertIsNotNone(AgentLoop)
        self.assertIsNotNone(Planner)
        self.assertIsNotNone(Executor)
        self.assertIsNotNone(Orchestrator)

    def test_llm_imports(self) -> None:
        """Verify LLM engine and provider imports."""
        from nexus_agent.llm import LLMProvider, LocalEngine, ModelManager, OnnxEngine, RuntimeManager, ProviderFactory
        from nexus_agent.llm.providers.openai_provider import OpenAIProvider
        self.assertIsNotNone(LLMProvider)
        self.assertIsNotNone(ProviderFactory)
        self.assertIsNotNone(OpenAIProvider)

    def test_memory_imports(self) -> None:
        """Verify memory imports."""
        from nexus_agent.memory.memory_manager import MemoryManager
        from nexus_agent.memory.working_memory import WorkingMemory
        from nexus_agent.memory.long_term import LongTermMemory
        self.assertIsNotNone(MemoryManager)

    def test_tools_imports(self) -> None:
        """Verify tool imports."""
        from nexus_agent.tools.base import Tool
        from nexus_agent.tools.file_ops import ReadFileTool, WriteFileTool
        from nexus_agent.tools.shell import ShellTool
        self.assertIsNotNone(Tool)

    def test_mcp_imports(self) -> None:
        """Verify MCP imports."""
        from nexus_agent.mcp import MCPClient, StdioTransport
        self.assertIsNotNone(MCPClient)
        self.assertIsNotNone(StdioTransport)
