"""Built-in tools for the agent — file ops, shell, code editing, git, search, RAG, batch edit, browser, code intel, LSP."""

from nexus_agent.tools.base import Tool
from nexus_agent.tools.batch_edit import BatchEditTool
from nexus_agent.tools.boomerang import BoomerangTool
from nexus_agent.tools.browser import BrowserTool
from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
from nexus_agent.tools.code_intel import CallGraphTool, ImportGraphTool, RenameTool
from nexus_agent.tools.council import CouncilTool
from nexus_agent.tools.file_ops import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from nexus_agent.tools.git_ops import CIAnalyzerTool, GitTool, PRGeneratorTool, SmartCommitTool
from nexus_agent.tools.lsp_client import LSPClientTool, register_lsp_server
from nexus_agent.tools.lsp_transport import (
    DEFAULT_SERVERS,
    LSPClient,
    LSPClientPool,
    LSPConfig,
    LSPError,
)
from nexus_agent.tools.rag_search import RepositoryRAGTool
from nexus_agent.tools.shell import ShellTool
from nexus_agent.tools.memory import MemoryTool
from nexus_agent.tools.todowrite import Todo, TodoPriority, TodoStatus, TodoStore, TodoWriteTool, format_todo_list
from nexus_agent.tools.web_search import WebSearchTool
from nexus_agent.tools.webfetch import WebFetchTool, html_to_markdown

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
    "WebFetchTool",
    "MemoryTool",
    "RepositoryRAGTool",
    "BatchEditTool",
    "BoomerangTool",
    "BrowserTool",
    "CouncilTool",
    "ImportGraphTool",
    "CallGraphTool",
    "RenameTool",
    "LSPClientTool",
    "LSPClient",
    "LSPClientPool",
    "LSPConfig",
    "LSPError",
    "DEFAULT_SERVERS",
    "register_lsp_server",
    "TodoWriteTool",
    "Todo",
    "TodoStatus",
    "TodoPriority",
    "TodoStore",
    "format_todo_list",
    "html_to_markdown",
]
