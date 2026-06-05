"""Commands package — slash command handlers organized by domain."""

from __future__ import annotations

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.cli.commands.agent import AgentCommands
from nexus_agent.cli.commands.config import ConfigCommands
from nexus_agent.cli.commands.debug import DebugCommands
from nexus_agent.cli.commands.git import GitCommands
from nexus_agent.cli.commands.misc import MiscCommands
from nexus_agent.cli.commands.model import ModelCommands
from nexus_agent.cli.commands.session import SessionCommands
from nexus_agent.cli.commands.tools import ToolsCommands

__all__ = [
    "BaseCommands",
    "AgentCommands",
    "ConfigCommands",
    "DebugCommands",
    "GitCommands",
    "MiscCommands",
    "ModelCommands",
    "SessionCommands",
    "ToolsCommands",
    "CommandDispatcherMixin",
]


class CommandDispatcherMixin(
    SessionCommands,
    ModelCommands,
    GitCommands,
    ToolsCommands,
    AgentCommands,
    ConfigCommands,
    DebugCommands,
    MiscCommands,
):
    """Aggregate mixin providing all slash command handlers.

    Inherits from all domain-specific mixin classes to provide
    the complete command dispatch interface expected by NexusApp.
    """
