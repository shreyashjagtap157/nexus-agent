"""Session orchestrator — session lifecycle, model loading, initialization."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from nexus_agent.cli.auth import AuthStore
from nexus_agent.cli.models_db import ModelsDB
from nexus_agent.cli.renderer import (
    PermissionDialog,
    detect_dark_mode,
    enable_vt_processing,
    strip_markup,
)
from nexus_agent.core.agent import AgentLoop, AgentLoopConfig
from nexus_agent.core.config import load_config
from nexus_agent.core.usage import UsageTracker
from nexus_agent.llm.model_manager import ModelManager
from nexus_agent.llm.runtime_manager import RuntimeManager
from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.permissions.rules import PermissionLevel
from nexus_agent.session.checkpoint import CheckpointManager
from nexus_agent.session.manager import SessionManager

logger = logging.getLogger(__name__)


class SessionOrchestratorMixin:
    """Mixin that provides session lifecycle management, model loading, and initialization."""

    def _initialize(self):
        enable_vt_processing()
        self._config = load_config(
            config_path=self.config_path,
            workspace=self.workspace,
            data_dir=self.data_dir,
        )

        theme_name = self._config.get("theme", "auto")
        if theme_name == "auto":
            theme_name = "dark" if detect_dark_mode() else "light"
        self.r.set_theme(theme_name)

        active_runtime_path = self._config.get("runtime", {}).get("path")
        if active_runtime_path:
            path_abs = os.path.abspath(os.path.expanduser(active_runtime_path))
            if os.path.exists(path_abs):
                path_dir = os.path.dirname(path_abs) if os.path.isfile(path_abs) else path_abs
                os.environ["PATH"] = path_dir + os.pathsep + os.environ.get("PATH", "")
                logger.info(f"Dynamically prepended custom runtime path: {path_dir}")

        if getattr(self, "_model_path_passed", False):
            self._model_path = self._model_path or self._config.get("model_path") or os.environ.get("NEXUS_MODEL_PATH")
        else:
            self._model_path = None

        data_dir_path = self._config.get("_data_dir", str(os.path.expanduser("~/.nexus-agent")))
        self._memory = MemoryManager(data_dir=f"{data_dir_path}/memory")
        project_mem_dir = self.workspace / ".nexus" / "memory"
        self._project_memory = MemoryManager(data_dir=str(project_mem_dir))
        self._session_mgr = SessionManager(data_dir=f"{data_dir_path}/sessions")
        self._checkpoint_mgr = CheckpointManager(os.path.join(data_dir_path, "checkpoints")) if self._session_mgr else None
        self._usage_tracker = UsageTracker(
            path=Path(data_dir_path) / "usage.json"
        )
        self._plugin_manager = PluginManager(
            workspace=self.workspace,
            plugin_dirs=[
                self.workspace / ".nexus" / "plugins",
                Path(data_dir_path) / "plugins",
            ]
        )
        self._plugin_manager.discover_and_load()

        self._permissions = PermissionManager(approval_callback=self._approval_handler)
        self._permissions.load_from_config(self._config)
        self._models_db = ModelsDB(data_dir=data_dir_path)
        self._auth_store = AuthStore(data_dir=data_dir_path)
        self._runtime_list: list = []

        loaded_keys = self._auth_store.load_into_env()
        if loaded_keys:
            logger.info(f"Loaded {loaded_keys} saved API key(s) from auth store")

        RuntimeManager(self._config)
        self._init_engine()
        self._mcp_clients: list = []
        self._mcp_tools: list = []
        self._skill_registry: Any = None
        self._init_mcp()
        self._init_skills()
        self._init_agent()

    def _init_engine(self, skip_interactive: bool = False):
        provider = self._provider_name or self._config.get("providers", {}).get("active", "local")
        from nexus_agent.llm.providers.factory import ProviderFactory

        try:
            model_val = self._model_path
            if provider == "local":
                local_config = self._config.setdefault("local_model", {})
                if self._gpu_layers is not None:
                    local_config["gpu_layers"] = self._gpu_layers
                if not model_val and getattr(self, "_model_path_passed", False):
                    mgr = ModelManager(models_dir=local_config.get("models_dir"))
                    best = mgr.find_best_model()
                    if best:
                        model_val = str(best)

                if sys.stdout.isatty() and model_val and not skip_interactive:
                    self._interactive_model_config(model_val)

            if provider == "local" and not model_val:
                self._engine = None
                self._model_status = "idle"
                return

            self._engine = ProviderFactory.create_provider(provider, self._config, model_val)
            if self._engine:
                self._model_status = "loaded"
            if model_val and os.path.isfile(str(model_val)):
                name = self._models_db.find_by_path(str(model_val))
                if not name:
                    name = self._models_db.auto_name(str(model_val))
                    self._models_db.add(name, str(model_val))
        except (ValueError, OSError, ImportError) as e:
            logger.error(f"Failed to create provider '{provider}': {e}")
            self._startup_error = f"Failed to load LLM provider '{provider}': {e}"
            self._engine = None
            self._model_status = "idle"

    def _init_mcp(self):
        mcp_config = self._config.get("mcp", {})
        servers = mcp_config.get("servers", [])
        for server_cfg in servers:
            command = server_cfg.get("command")
            if not command:
                continue
            try:
                from nexus_agent.mcp.client import MCPClient
                client = MCPClient(command=[command] + server_cfg.get("args", []),
                                   env=server_cfg.get("env"))
                if client.start():
                    self._mcp_clients.append(client)
                    self._mcp_tools.extend(client.discovered_tools)
                    logger.info(f"MCP server connected: {command}")
            except (OSError, ValueError, ConnectionError) as e:
                logger.warning(f"MCP server failed to start ({command}): {e}")

    def _init_skills(self):
        try:
            from nexus_agent.skills.skill_registry import SkillRegistry
            skill_dirs = self._config.get("skills", {}).get("search_dirs")
            self._skill_registry = SkillRegistry(
                search_dirs=skill_dirs,
                workspace=self.workspace,
            )
            discovered = self._skill_registry.discover_skills()
            if discovered:
                logger.info(f"Discovered {len(discovered)} skills")
        except (ImportError, OSError, ValueError) as e:
            logger.warning(f"Skill registry init: {e}")
            self._skill_registry = None

    def _init_agent(self):
        if not self._engine:
            return

        from nexus_agent.tools.batch_edit import BatchEditTool
        from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
        from nexus_agent.tools.code_intel import ImportGraphTool
        from nexus_agent.tools.file_ops import (
            ListDirectoryTool,
            ReadFileTool,
            SearchFilesTool,
            WriteFileTool,
        )
        from nexus_agent.tools.git_ops import GitTool
        from nexus_agent.tools.memory import MemoryTool
        from nexus_agent.tools.rag_search import RepositoryRAGTool
        from nexus_agent.tools.shell import ShellTool
        from nexus_agent.tools.todowrite import TodoWriteTool
        from nexus_agent.tools.web_search import WebSearchTool
        from nexus_agent.tools.webfetch import WebFetchTool

        tools = [
            ReadFileTool(self.workspace),
            WriteFileTool(self.workspace),
            SearchFilesTool(self.workspace),
            ListDirectoryTool(self.workspace),
            ShellTool(self.workspace),
            CodeEditTool(self.workspace),
            InsertLinesTool(self.workspace),
            GitTool(self.workspace),
            WebSearchTool(),
            WebFetchTool(),
            RepositoryRAGTool(self.workspace),
            BatchEditTool(self.workspace),
            ImportGraphTool(self.workspace),
            TodoWriteTool(persist_path=self.workspace / ".nexus" / "todos.json"),
        ]
        # Load plugin tools
        plugin_manager = getattr(self, "_plugin_manager", None)
        if plugin_manager:
            for info in plugin_manager.plugins.values():
                tools.extend(info.tools)
        # MemoryTool needs the MemoryManager to be constructed first, so
        # it's bound after the tools list is built.
        memory_tool = MemoryTool()
        if self._memory is not None:
            memory_tool.set_memory(self._memory)
        tools.append(memory_tool)

        mcp_tools = getattr(self, "_mcp_tools", [])
        if mcp_tools:
            tools.extend(mcp_tools)

        try:
            from nexus_agent.tools.browser import BrowserTool
            tools.append(BrowserTool())
        except ImportError as e:
            logger.debug(f"Browser tool not available: {e}")

        try:
            from nexus_agent.tools.lsp_client import LSPClientTool
            tools.append(LSPClientTool(self.workspace))
        except ImportError as e:
            logger.debug(f"LSP tool not available: {e}")

        memory_context = ""
        if self._memory:
            try:
                memory_context = self._memory.get_context_for_prompt()
            except (OSError, ValueError):
                pass

        cfg = AgentLoopConfig(
            mode=self._current_mode,
            workspace=self.workspace,
            max_iterations=self._config.get("agent", {}).get("max_iterations", 50),
            temperature=self._config.get("agent", {}).get("temperature", 0.1),
            max_tokens=self._config.get("agent", {}).get("max_tokens", 4096),
            permission_callback=self._permission_handler,
            system_prompt_extra=memory_context,
            effort_level=self._config.get("agent", {}).get("effort_level", "medium"),
            goal=self._config.get("agent", {}).get("goal", ""),
        )

        self._agent = AgentLoop(
            provider=self._engine,
            tools=tools,
            config=cfg,
            usage_tracker=getattr(self, "_usage_tracker", None),
        )

        if self._session_mgr:
            if not self._session_id and not getattr(self, "_new_session", False):
                last_sid = self._session_mgr.get_last_session_for_workspace(str(self.workspace))
                if last_sid:
                    self._session_id = last_sid
                    logger.info(f"Auto-resumed last session for workspace: {self._session_id}")

            if self._session_id:
                s_data = self._session_mgr.resume_session(self._session_id)
                if s_data and "mode" in s_data:
                    try:
                        from nexus_agent.core.agent import AgentMode
                        self._current_mode = AgentMode(s_data["mode"])
                        if self._agent:
                            self._agent.mode = self._current_mode
                        self._replay_session_history(s_data)
                        self._restore_agent_context(s_data.get("messages", []))
                    except ValueError:
                        pass
            else:
                self._session_id = self._session_mgr.create_session(
                    model=self._engine.model_name if self._engine else "unknown",
                    provider=self._provider_name or "local",
                    workspace=str(self.workspace),
                    mode=self._current_mode.value,
                )

        mcp_count = len(self._mcp_tools) if self._mcp_tools else 0
        skills_count = len(self._skill_registry.list_skills()) if self._skill_registry and hasattr(self._skill_registry, 'list_skills') else 0
        self._context.update_from_agent(
            agent=self._agent,
            engine=self._engine,
            mcp_tools_count=mcp_count,
            skills_count=skills_count,
        )

        # Expose the usage tracker to the dispatcher (for /cost).
        self.usage_tracker = getattr(self, "_usage_tracker", None)
        self.plugin_manager = getattr(self, "_plugin_manager", None)

        if self._engine:
            prov_name = getattr(self._engine, 'name', self._provider_name or 'local')
            self._tokens.provider_name = prov_name
            self._tokens.context_window = self._context.max_context

    def _model_name(self) -> str:
        if self._engine and getattr(self._engine, "is_loaded", True):
            try:
                name = getattr(self._engine, "model_name", "")[:55] or "loaded"
                prov = getattr(self._engine, "name", "")
                return f"{name} via {prov}" if prov else name
            except (AttributeError, TypeError):
                return "loaded"
        return self._model_path or "no model"

    def _check_resize(self) -> bool:
        try:
            h = shutil.get_terminal_size().lines
            w = shutil.get_terminal_size().columns
        except (OSError, ValueError):
            return False
        if h != self._last_term_h or w != self.r.width:
            self._last_term_h = h
            self.r.update_size()
            if self.r._is_fullscreen:
                self.r._render_fullscreen()
            else:
                self._rebuild_welcome()
            return True
        return False

    def _check_resize_in_loop(self) -> bool:
        return self._check_resize()

    def _refresh_status(self, render: bool = False):
        model = self._model_name()
        mode = self._current_mode.value.upper()
        effort = self._config.get("agent", {}).get("effort_level", "medium").upper()
        tokens_short = self._tokens.display_short()
        ctx_display = self._tokens.display_context()

        items = [f"[bold]{model[:40]}[/bold]", f"Mode: [bold]{mode}[/bold]", f"/{effort}", tokens_short, ctx_display]

        cost = self._tokens.estimated_cost
        if cost > 0:
            items.append(f"[dim]${cost:.4f}[/dim]")

        if self._sub_agents:
            items.append(f"[cyan]⊞ {len(self._sub_agents)} agents[/cyan]")

        if self._agent and self._agent.goal:
            goal = self._agent.goal[:25]
            items.append(f"[yellow]🎯 {goal}[/yellow]")

        self.r.update_status(*items)
        self.r.set_terminal_title(self._status_line())
        if render:
            self.r.console.print()
            self.r.status_bar.render_to(self.r.console)
            self.r.console.print()

    def _get_resource_info(self) -> str:
        parts = []
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            parts.append(f"CPU:{cpu:.0f}%")
            ram = psutil.virtual_memory()
            parts.append(f"RAM:{ram.percent:.0f}%")
            used_gb = ram.used / (1024**3)
            if used_gb >= 1:
                parts.append(f"{used_gb:.1f}G")
        except (ImportError, ValueError, OSError):
            pass
        try:
            import torch
            if torch.cuda.is_available():
                gpu_mem = torch.cuda.memory_allocated() / (1024**3)
                gpu_reserved = torch.cuda.memory_reserved() / (1024**3)
                parts.append(f"GPU:{gpu_mem:.1f}G")
        except (ImportError, RuntimeError, ValueError):
            pass
        try:
            du = shutil.disk_usage("/")
            used_pct = (du.used / du.total) * 100
            parts.append(f"Disk:{used_pct:.0f}%")
        except (OSError, ValueError):
            pass
        return "  ".join(parts)

    def _rebuild_welcome(self):
        model_name = strip_markup(self._model_name())
        provider = self._provider_name or "local"
        if self._first_request_done:
            res_info = self._get_resource_info()
        else:
            res_info = ""
        if hasattr(self.r, 'rebuild_welcome'):
            self.r.rebuild_welcome(
                self._tokens, self._metrics,
                model_status=self._model_status,
                resource_info=res_info,
                active_agents=len(self._sub_agents),
            )
        self.r.set_terminal_title(self._status_line())

    def _status_line(self) -> str:
        model = strip_markup(self._model_name())
        mode = self._current_mode.value.upper()
        return f"NexusAgent | {model} | {mode} | {self._tokens.total}t"

    def _permission_handler(self, tool_call: Any) -> bool:
        if not self._permissions:
            return True

        level = self._permissions.evaluate(tool_call.name, tool_call.arguments)
        if level == PermissionLevel.ALLOW:
            return True
        if level == PermissionLevel.DENY:
            self.r.system_message(f"Blocked: {tool_call.name}")
            return False

        return PermissionDialog.render(self.console, tool_call.name, tool_call.arguments)

    def _approval_handler(self, tool_name: str, description: str, arguments: dict) -> bool:
        return PermissionDialog.render(self.console, tool_name, arguments)

    def _replay_session_history(self, session_data: dict[str, Any]) -> None:
        """Replay session history in condensed format on resume.

        Args:
            session_data: Session data dict from resume_session containing messages.
        """
        if not session_data:
            return

        messages = session_data.get("messages", [])
        if not messages:
            return

        session_id = session_data.get("id", "")
        message_count = len(messages)
        created = session_data.get("created", "")

        self.r.replay_session_header(session_id, message_count, created)

        for msg in messages:
            msg_type = msg.get("type", "")
            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            name = msg.get("name", "")
            metadata = msg.get("metadata", {}) or {}
            tool_calls = msg.get("tool_calls")

            if msg_type == "user" or role == "user":
                self.r.replay_user_message(content)
            elif msg_type == "assistant" or role == "assistant":
                self.r.replay_assistant_message(content)
            elif msg_type == "tool_call" or (role == "assistant" and tool_calls):
                tool_name = name
                args = {}
                if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                    tc = tool_calls[0]
                    tool_name = tc.get("name", name)
                    args = tc.get("arguments", {})
                self.r.replay_tool_call(tool_name, args)
            elif msg_type == "tool_result" or role == "tool":
                success = metadata.get("success", True)
                elapsed = metadata.get("elapsed", 0.0)
                self.r.replay_tool_result(name or "tool", success, elapsed)
            elif msg_type == "system" or role == "system":
                self.r.replay_system_message(content)
            elif msg_type == "divider":
                self.r.replay_divider()
            elif content:
                self.r.replay_system_message(content[:100])

        self.r.replay_divider()
        self.r.console.print()

    def _restore_agent_context(self, messages: list[dict[str, Any]]) -> None:
        """Restore the agent's messages list from stored session messages.

        Args:
            messages: List of stored message dicts from session storage.
        """
        if not self._agent or not messages:
            return

        try:
            from nexus_agent.core.agent import Message, Role
        except ImportError:
            logger.warning("Could not import Message class for context restoration")
            return

        restored = []
        for msg in messages:
            role_str = msg.get("role", "user")
            content = msg.get("content", "") or ""

            if role_str == "system":
                continue

            try:
                role = Role(role_str)
            except ValueError:
                role = Role.USER

            tool_calls = msg.get("tool_calls")
            tool_call_id = msg.get("tool_call_id")
            name = msg.get("name")

            restored.append(Message(
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                name=name,
            ))

        if restored:
            self._agent.messages = restored
            logger.info(f"Restored {len(restored)} messages to agent context")

            if self._engine and hasattr(self._engine, 'count_message_tokens'):
                try:
                    total_tokens = self._engine.count_message_tokens(restored)
                    self._tokens.input_tokens = total_tokens
                    self._tokens.total_input = total_tokens
                    logger.info(f"Estimated {total_tokens} tokens for restored context")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not estimate token count: {e}")
