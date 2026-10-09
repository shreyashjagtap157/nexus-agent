"""Runtime control registry for multi-agent teams."""

from __future__ import annotations

import threading


class TeamControl:
    def __init__(self) -> None:
        self.pause_requested = threading.Event()
        self.stop_requested = threading.Event()


_LOCK = threading.RLock()
_CONTROLS: dict[str, TeamControl] = {}


def register(team_id: str) -> TeamControl:
    control = TeamControl()
    with _LOCK:
        _CONTROLS[team_id] = control
    return control


def unregister(team_id: str) -> None:
    with _LOCK:
        _CONTROLS.pop(team_id, None)


def control(team_id: str, action: str) -> bool:
    with _LOCK:
        item = _CONTROLS.get(team_id)
    if item is None:
        return False
    action = action.strip().lower()
    if action == "pause":
        item.pause_requested.set()
        return True
    if action == "resume":
        item.pause_requested.clear()
        return True
    if action == "stop":
        item.stop_requested.set()
        return True
    return False
