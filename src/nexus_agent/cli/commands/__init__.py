"""Commands package — slash command handlers organized by domain.

Re-exports CommandDispatcherMixin from command_dispatcher.py as the
single aggregate mixin for NexusApp. Individual mixins are imported
directly by command_dispatcher.py.
"""

from __future__ import annotations

from nexus_agent.cli.command_dispatcher import CommandDispatcherMixin
from nexus_agent.cli.commands.model_mixin import ModelCommandsMixin

__all__ = ["CommandDispatcherMixin", "ModelCommandsMixin"]
