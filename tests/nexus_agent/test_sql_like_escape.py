from __future__ import annotations

import sqlite3

from nexus_agent.utils.sql import escape_like_pattern


def test_like_pattern_escapes_backslash_before_wildcards() -> None:
    assert escape_like_pattern(r"a\\b%c_d") == r"a\\\\b\%c\_d"


def test_like_pattern_matches_literal_wildcards_only() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE items (content TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO items(content) VALUES (?)",
        [("prefix \\%_ suffix",), ("prefix AX suffix",), ("prefix \\abc suffix",)],
    )
    needle = r"\\%_"
    pattern = f"%{escape_like_pattern(needle)}%"
    matches = conn.execute(
        "SELECT content FROM items WHERE content LIKE ? ESCAPE \\?",
        (pattern,),
    ).fetchall()
    assert matches == [("prefix \\%_ suffix",)]
    conn.close()
