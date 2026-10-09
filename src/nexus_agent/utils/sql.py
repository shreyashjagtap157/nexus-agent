"""Safe escaping for parameterized SQLite LIKE expressions."""
from __future__ import annotations


def escape_like_pattern(value: str) -> str:
    """Escape SQLite LIKE metacharacters for use with a backslash ESCAPE clause.

    Escape the escape character first; otherwise an input backslash can consume
    the escape inserted before percent or underscore and restore wildcard behavior.
    """
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
