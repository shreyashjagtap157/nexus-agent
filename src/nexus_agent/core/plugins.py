"""
Plugin/Extension System — Dynamic command & tool registration.

Allows third-party or local python files in `.nexus/plugins/` and
configured folders to load into the agent dynamically. Plugins can
expose new slash commands, new tools, or pre/post hooks.

A plugin file is a Python module that defines a class or function:
`def register_plugin(manager: PluginManager) -> None`
or has a subclass of `NexusPlugin` that is auto-discovered.
"""

from __future__ import annotations

import importlib.machinery
import importlib.metadata
import importlib.util
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class NexusPlugin:
    """Base class for NexusAgent plugins.

    Plugins can inherit from this class to participate in auto-discovery.
    """

    def __init__(self, manager: PluginManager) -> None:
        self.manager = manager
        self.name: str = ""

    def initialize(self) -> None:
        """Called immediately after loading to register commands, tools, etc."""
        pass


@dataclass
class PluginInfo:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    path: Path | None = None
    plugin_instance: Any = None
    commands: dict[str, Callable[[Any, str], None]] = field(default_factory=dict)
    tools: list[Any] = field(default_factory=list)
    error: str | None = None


class PluginManager:
    """Orchestrates dynamic discovery, loading, and registration of plugins."""

    def __init__(self, workspace: Path | None = None, plugin_dirs: list[Path] | None = None) -> None:
        self.workspace = workspace or Path.cwd()
        self.plugin_dirs = plugin_dirs or [
            self.workspace / ".nexus" / "plugins",
            Path("~/.nexus-agent/plugins").expanduser(),
        ]
        self.plugins: dict[str, PluginInfo] = {}

    def discover_and_load(self) -> dict[str, PluginInfo]:
        """Scans plugin directories and loads Python files as plugins."""
        self.plugins.clear()

        # 1. Discover local directory-based plugins
        for directory in self.plugin_dirs:
            if not directory.exists() or not directory.is_dir():
                continue
            for file_path in directory.glob("*.py"):
                if file_path.name.startswith("_"):
                    continue
                self._load_file_plugin(file_path)

        # 2. Discover standard python packaging entry points (pluggy-like)
        self._load_entry_points()

        return dict(self.plugins)

    def register_command(self, plugin_name: str, command_name: str, callback: Callable[[Any, str], None]) -> None:
        """Expose a slash command from a plugin.

        The command name must start with a slash (e.g., '/mycmd').
        """
        if not command_name.startswith("/"):
            command_name = f"/{command_name}"
        if plugin_name in self.plugins:
            self.plugins[plugin_name].commands[command_name] = callback
            logger.info(f"Registered plugin command: {command_name} from {plugin_name}")

    def register_tool(self, plugin_name: str, tool_instance: Any) -> None:
        """Expose a Tool from a plugin to be appended to the AgentLoop."""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].tools.append(tool_instance)
            logger.info(f"Registered plugin tool: {getattr(tool_instance, 'name', type(tool_instance).__name__)} from {plugin_name}")

    def _load_file_plugin(self, file_path: Path) -> None:
        name = file_path.stem
        info = PluginInfo(name=name, path=file_path)

        try:
            # Load Python file dynamically
            loader = importlib.machinery.SourceFileLoader(f"nexus_plugin_{name}", str(file_path))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not build module spec for {file_path}")
            module = importlib.util.module_from_spec(spec)
            # Add to sys.modules to allow relative imports inside plugins
            sys.modules[loader.name] = module
            spec.loader.exec_module(module)

            # Try to find register_plugin function or NexusPlugin subclass
            registered = False

            # Option A: register_plugin(manager) function
            register_func = getattr(module, "register_plugin", None)
            if register_func and callable(register_func):
                self.plugins[name] = info
                register_func(self)
                registered = True

            # Option B: Any class inheriting from NexusPlugin
            if not registered:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, NexusPlugin)
                        and attr is not NexusPlugin
                    ):
                        self.plugins[name] = info
                        instance = attr(self)
                        instance.name = name
                        info.plugin_instance = instance
                        instance.initialize()
                        registered = True
                        break

            if not registered:
                info.error = "No entry point ('register_plugin' function or 'NexusPlugin' subclass) found."
                self.plugins[name] = info

        except Exception as e:
            logger.warning(f"PluginManager: Failed to load {file_path}: {e}")
            info.error = str(e)
            self.plugins[name] = info

    def _load_entry_points(self) -> None:
        """Load plugins registered under package entry points 'nexus_agent.plugins'."""
        group = importlib.metadata.entry_points(group="nexus_agent.plugins")


        for ep in group:
            name = ep.name
            info = PluginInfo(name=name)
            try:
                module = ep.load()
                register_func = getattr(module, "register_plugin", None)
                if register_func and callable(register_func):
                    self.plugins[name] = info
                    register_func(self)
                else:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, NexusPlugin)
                            and attr is not NexusPlugin
                        ):
                            self.plugins[name] = info
                            instance = attr(self)
                            instance.name = name
                            info.plugin_instance = instance
                            instance.initialize()
                            break
            except Exception as e:
                logger.warning(f"PluginManager: Failed to load entrypoint plugin {name}: {e}")
                info.error = str(e)
                self.plugins[name] = info
