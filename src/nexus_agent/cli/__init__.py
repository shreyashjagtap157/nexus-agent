"""NexusAgent CLI — Claude Code-style inline terminal interface.

Uses Rich for rendering with a Claude Code-inspired design:
- Inline (scrollback) mode by default, fullscreen optional
- Spinner with fun verbs (Warping, Discombobulating, etc.)
- Status bar with model, mode, token counts, context window
- Slash command menu with autocomplete
- @-mention file autocomplete
- Streaming token display
- Sub-agent reporting
"""

from nexus_agent.cli.app import NexusApp
from nexus_agent.cli.auth import AuthStore
from nexus_agent.cli.models_db import ModelsDB
from nexus_agent.cli.renderer import NexusTerminalRenderer, Verbosity

__all__ = [
    "NexusApp",
    "AuthStore",
    "ModelsDB",
    "NexusTerminalRenderer",
    "Verbosity",
]
