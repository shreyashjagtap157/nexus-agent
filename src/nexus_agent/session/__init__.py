"""Session management — persistence, checkpoints, and rollback."""

from __future__ import annotations

from nexus_agent.session.background import (
    BackgroundResult,
    BackgroundSession,
    BackgroundState,
)
from nexus_agent.session.checkpoint import Checkpoint, CheckpointManager
from nexus_agent.session.manager import SCHEMA_VERSION, SessionManager
from nexus_agent.session.storage import SessionStorage

__all__ = [
    "SessionManager",
    "SessionStorage",
    "CheckpointManager",
    "Checkpoint",
    "BackgroundSession",
    "BackgroundResult",
    "BackgroundState",
    "SCHEMA_VERSION",
]
