"""Built-in tools for the agent — file ops, shell, code editing, git, search, RAG, batch edit, browser, code intel, LSP."""

from nexus_agent.tools.base import Tool
from nexus_agent.tools.batch_edit import BatchEditTool
from nexus_agent.tools.browser import BrowserTool
from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
from nexus_agent.tools.code_intel import CallGraphTool, ImportGraphTool, RenameTool
from nexus_agent.tools.file_ops import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from nexus_agent.tools.git_ops import CIAnalyzerTool, GitTool, PRGeneratorTool, SmartCommitTool
from nexus_agent.tools.lsp_client import LSPClientTool
from nexus_agent.tools.rag_search import RepositoryRAGTool
from nexus_agent.tools.shell import ShellTool
from nexus_agent.tools.web_search import WebSearchTool

__all__ = [
    "Tool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchFilesTool",
    "ListDirectoryTool",
    "ShellTool",
    "CodeEditTool",
    "InsertLinesTool",
    "GitTool",
    "SmartCommitTool",
    "PRGeneratorTool",
    "CIAnalyzerTool",
    "WebSearchTool",
    "RepositoryRAGTool",
    "BatchEditTool",
    "BrowserTool",
    "ImportGraphTool",
    "CallGraphTool",
    "RenameTool",
    "LSPClientTool",
]
