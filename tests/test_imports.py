"""Test that all package modules can be imported without errors."""

import pytest


class TestCoreImports:
    """Test core module imports."""

    def test_import_nexus_agent(self):
        import nexus_agent
        assert hasattr(nexus_agent, "__version__")
        assert nexus_agent.__version__ == "0.1.0"

    def test_import_agent_loop(self):
        from nexus_agent.core.agent import AgentLoop, AgentLoopConfig, AgentMode, AgentState
        assert AgentMode.AUTO.value == "auto"

    def test_import_config(self):
        from nexus_agent.core.config import load_config, save_config, save_user_config
        assert callable(load_config)

    def test_import_context(self):
        from nexus_agent.core.context import ContextManager, ContextStats
        assert callable(ContextManager)

    def test_import_sandbox(self):
        from nexus_agent.core.sandbox import Sandbox, SandboxConfig, SandboxMode, CommandRisk
        assert SandboxMode.ASK.value == "ask"

    def test_import_orchestrator(self):
        from nexus_agent.core.orchestrator import Orchestrator, BoomerangSubTask
        assert callable(Orchestrator)

    def test_import_planner(self):
        from nexus_agent.core.planner import Planner
        assert callable(Planner)

    def test_import_executor(self):
        from nexus_agent.core.executor import Executor
        assert callable(Executor)

    def test_import_debate(self):
        from nexus_agent.core.debate import DebateEngine, DebateVerdict
        assert callable(DebateEngine)

    def test_import_devops(self):
        from nexus_agent.core.devops import VerificationPipeline, PipelineReport
        assert callable(VerificationPipeline)

    def test_import_nla_telemetry(self):
        from nexus_agent.core.nla_telemetry import NLATelemetry, NLARecord
        assert callable(NLATelemetry)

    def test_import_reflection(self):
        from nexus_agent.core.reflection import ReflectionEngine, CritiqueResult
        assert callable(ReflectionEngine)

    def test_import_self_heal(self):
        from nexus_agent.core.self_heal import SelfHealingExecutor, FailureClassifier
        assert callable(SelfHealingExecutor)

    def test_import_task_graph(self):
        from nexus_agent.core.task_graph import TaskGraph, TaskNode
        assert callable(TaskGraph)

    def test_import_plugins(self):
        from nexus_agent.core.plugins import PluginManager, NexusPlugin
        assert callable(PluginManager)

    def test_import_usage(self):
        from nexus_agent.core.usage import UsageTracker, UsageEntry
        assert callable(UsageTracker)

    def test_import_updater(self):
        from nexus_agent.core.updater import check_for_update, UpdateInfo
        assert callable(check_for_update)

    def test_import_project_context(self):
        from nexus_agent.core.project_context import ProjectContextLoader
        assert callable(ProjectContextLoader)

    def test_import_sqlite_store(self):
        from nexus_agent.core.sqlite_store import SQLiteStore
        assert callable(SQLiteStore)


class TestLLMImports:
    """Test LLM module imports."""

    def test_import_base(self):
        from nexus_agent.llm.base import LLMProvider, Message, Role, ToolCall, LLMResponse
        assert Role.SYSTEM.value == "system"

    def test_import_retry(self):
        from nexus_agent.llm.retry import RetryPolicy, with_retry, RetryProvider
        assert callable(with_retry)

    def test_import_runtime_manager(self):
        from nexus_agent.llm.runtime_manager import RuntimeManager, SmartRouter
        assert callable(RuntimeManager)

    def test_import_model_manager(self):
        from nexus_agent.llm.model_manager import ModelManager
        assert callable(ModelManager)

    def test_import_provider_factory(self):
        from nexus_agent.llm.providers.factory import ProviderFactory
        assert callable(ProviderFactory)

    def test_import_openai_provider(self):
        from nexus_agent.llm.providers.openai_provider import OpenAIProvider
        assert callable(OpenAIProvider)

    def test_import_anthropic_provider(self):
        from nexus_agent.llm.providers.anthropic_provider import AnthropicProvider
        assert callable(AnthropicProvider)

    def test_import_google_provider(self):
        from nexus_agent.llm.providers.google_provider import GoogleProvider
        assert callable(GoogleProvider)

    def test_import_ollama_provider(self):
        from nexus_agent.llm.providers.ollama_provider import OllamaProvider
        assert callable(OllamaProvider)


class TestToolImports:
    """Test tool module imports."""

    def test_import_tool_base(self):
        from nexus_agent.tools.base import Tool, ToolError, format_aci_output
        assert callable(format_aci_output)

    def test_import_file_ops(self):
        from nexus_agent.tools.file_ops import ReadFileTool, WriteFileTool, SearchFilesTool, ListDirectoryTool
        assert callable(ReadFileTool)

    def test_import_shell(self):
        from nexus_agent.tools.shell import ShellTool
        assert callable(ShellTool)

    def test_import_code_edit(self):
        from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
        assert callable(CodeEditTool)

    def test_import_git_ops(self):
        from nexus_agent.tools.git_ops import GitTool
        assert callable(GitTool)

    def test_import_web_search(self):
        from nexus_agent.tools.web_search import WebSearchTool
        assert callable(WebSearchTool)

    def test_import_webfetch(self):
        from nexus_agent.tools.webfetch import WebFetchTool
        assert callable(WebFetchTool)

    def test_import_memory_tool(self):
        from nexus_agent.tools.memory import MemoryTool
        assert callable(MemoryTool)

    def test_import_todowrite(self):
        from nexus_agent.tools.todowrite import TodoWriteTool
        assert callable(TodoWriteTool)

    def test_import_boomerang(self):
        from nexus_agent.tools.boomerang import BoomerangTool
        assert callable(BoomerangTool)

    def test_import_council(self):
        from nexus_agent.tools.council import CouncilTool
        assert callable(CouncilTool)

    def test_import_batch_edit(self):
        from nexus_agent.tools.batch_edit import BatchEditTool
        assert callable(BatchEditTool)

    def test_import_rag_search(self):
        from nexus_agent.tools.rag_search import RepositoryRAGTool
        assert callable(RepositoryRAGTool)

    def test_import_code_intel(self):
        from nexus_agent.tools.code_intel import ImportGraphTool
        assert callable(ImportGraphTool)


class TestMemoryImports:
    """Test memory module imports."""

    def test_import_memory_manager(self):
        from nexus_agent.memory.memory_manager import MemoryManager
        assert callable(MemoryManager)

    def test_import_working_memory(self):
        from nexus_agent.memory.working_memory import WorkingMemory
        assert callable(WorkingMemory)

    def test_import_long_term(self):
        from nexus_agent.memory.long_term import LongTermMemory
        assert callable(LongTermMemory)

    def test_import_episodic(self):
        from nexus_agent.memory.episodic import EpisodicMemory
        assert callable(EpisodicMemory)

    def test_import_user_profile(self):
        from nexus_agent.memory.user_profile import UserProfile
        assert callable(UserProfile)

    def test_import_vector_store(self):
        from nexus_agent.memory.vector_store import VectorStore
        assert callable(VectorStore)


class TestSessionImports:
    """Test session module imports."""

    def test_import_session_manager(self):
        from nexus_agent.session.manager import SessionManager
        assert callable(SessionManager)

    def test_import_session_storage(self):
        from nexus_agent.session.storage import SessionStorage
        assert callable(SessionStorage)

    def test_import_checkpoint(self):
        from nexus_agent.session.checkpoint import CheckpointManager, Checkpoint
        assert callable(CheckpointManager)


class TestPermissionImports:
    """Test permission module imports."""

    def test_import_permission_manager(self):
        from nexus_agent.permissions.manager import PermissionManager
        assert callable(PermissionManager)

    def test_import_permission_rules(self):
        from nexus_agent.permissions.rules import PermissionLevel, PermissionRule, DEFAULT_RULES
        assert PermissionLevel.ALLOW.value == "allow"
        assert len(DEFAULT_RULES) > 0


class TestMCPImports:
    """Test MCP module imports."""

    def test_import_mcp_client(self):
        from nexus_agent.mcp.client import MCPClient
        assert callable(MCPClient)

    def test_import_mcp_server(self):
        from nexus_agent.mcp.server import MCPServer
        assert callable(MCPServer)

    def test_import_transport(self):
        from nexus_agent.mcp.transport import StdioTransport
        assert callable(StdioTransport)

    def test_import_acp_server(self):
        from nexus_agent.mcp.acp_server import ACPServer
        assert callable(ACPServer)


class TestSkillImports:
    """Test skill module imports."""

    def test_import_skill_loader(self):
        from nexus_agent.skills.skill_loader import Skill, load_skill_from_markdown
        assert callable(load_skill_from_markdown)

    def test_import_skill_registry(self):
        from nexus_agent.skills.skill_registry import SkillRegistry
        assert callable(SkillRegistry)


class TestCLIImports:
    """Test CLI module imports."""

    def test_import_main(self):
        from nexus_agent.__main__ import main, cli
        assert callable(main)

    def test_import_renderer(self):
        from nexus_agent.cli.renderer import (
            NexusTerminalRenderer, TokenUsage, ContextBreakdown,
            Verbosity, PermissionDialog, detect_dark_mode,
            enable_vt_processing, strip_markup, SPINNER_VERBS_PRESENT
        )
        assert len(SPINNER_VERBS_PRESENT) > 0

    def test_import_input_handler(self):
        from nexus_agent.cli.input_handler import InputHandlerMixin
        assert callable(InputHandlerMixin)

    def test_import_session_handler(self):
        from nexus_agent.cli.session_handler import SessionOrchestratorMixin
        assert callable(SessionOrchestratorMixin)

    def test_import_event_handler(self):
        from nexus_agent.cli.event_handler import EventHandlerMixin
        assert callable(EventHandlerMixin)

    def test_import_auth(self):
        from nexus_agent.cli.auth import AuthStore
        assert callable(AuthStore)

    def test_import_models_db(self):
        from nexus_agent.cli.models_db import ModelsDB
        assert callable(ModelsDB)

    def test_import_wizard(self):
        from nexus_agent.cli.wizard import SetupWizard
        assert callable(SetupWizard)

    def test_import_theme(self):
        from nexus_agent.cli.theme import ThemeColors
        assert callable(ThemeColors)

    def test_import_resource_monitor(self):
        from nexus_agent.cli.resource_monitor import ResourceMonitor
        assert callable(ResourceMonitor)

    def test_import_runtimes(self):
        from nexus_agent.cli.runtimes import RuntimeInfo
        assert callable(RuntimeInfo)

    def test_import_doctor(self):
        from nexus_agent.cli.doctor import run_doctor, print_report
        assert callable(run_doctor)

    def test_import_command_dispatcher(self):
        from nexus_agent.cli.command_dispatcher import CommandDispatcherMixin, SLASH_COMMANDS
        assert len(SLASH_COMMANDS) > 50

    def test_import_agent_mixin(self):
        from nexus_agent.cli.commands.agent_mixin import AgentCommandsMixin
        assert callable(AgentCommandsMixin)

    def test_import_config_mixin(self):
        from nexus_agent.cli.commands.config_mixin import ConfigCommandsMixin
        assert callable(ConfigCommandsMixin)

    def test_import_debug_mixin(self):
        from nexus_agent.cli.commands.debug_mixin import DebugCommandsMixin
        assert callable(DebugCommandsMixin)

    def test_import_interactive_mixin(self):
        from nexus_agent.cli.commands.interactive_mixin import InteractiveCommandsMixin
        assert callable(InteractiveCommandsMixin)

    def test_import_misc_mixin(self):
        from nexus_agent.cli.commands.misc_mixin import MiscCommandsMixin
        assert callable(MiscCommandsMixin)

    def test_import_model_mixin(self):
        from nexus_agent.cli.commands.model_mixin import ModelCommandsMixin
        assert callable(ModelCommandsMixin)

    def test_import_provider_mixin(self):
        from nexus_agent.cli.commands.provider_mixin import ProviderCommandsMixin
        assert callable(ProviderCommandsMixin)

    def test_import_runtime_mixin(self):
        from nexus_agent.cli.commands.runtime_mixin import RuntimeCommandsMixin
        assert callable(RuntimeCommandsMixin)

    def test_import_session_mixin(self):
        from nexus_agent.cli.commands.session_mixin import SessionCommandsMixin
        assert callable(SessionCommandsMixin)

    def test_import_tool_mixin(self):
        from nexus_agent.cli.commands.tool_mixin import ToolCommandsMixin
        assert callable(ToolCommandsMixin)


class TestGUIImports:
    """Test GUI module imports."""

    def test_import_gui_server(self):
        from nexus_agent.gui.server import app
        assert app is not None
