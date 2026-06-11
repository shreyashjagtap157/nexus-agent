"""RAG Search Tool — Offline repository semantic keyword search via SQLite FTS5 & code symbol matching."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class RepositoryRAGTool(Tool):
    """Offline repository search tool utilizing SQLite FTS5 index.

    Parses workspace code files, chunks them into segments, and indexes them
    for fast retrieval, making offline RAG analysis clean and vector-free.
    Supports a state-of-the-art hybrid index mapping syntactic symbols
    (classes/functions) to boost structural keyword matching precision.
    """

    def __init__(self, workspace: Path, db_dir: Path | None = None):
        super().__init__()
        self.workspace = Path(workspace).resolve()

        # Determine RAG db path (workspace-sandboxed to prevent cross-project code leakage)
        target_dir = db_dir or (self.workspace / ".nexus-agent").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = target_dir / "rag.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def __enter__(self) -> RepositoryRAGTool:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return (
            "Perform an offline RAG keyword search across the entire workspace repository. "
            "Returns relevant file chunks and snippets matching your query, prioritizing "
            "syntactic code symbols like classes and functions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "Search query or keyword pattern to find inside code files.",
            },
            "reindex": {
                "type": "boolean",
                "description": "Force scan and rebuild of the repository FTS5 index before querying.",
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["query"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS file_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER
            );

            CREATE TABLE IF NOT EXISTS code_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                symbol_name TEXT NOT NULL,
                symbol_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_code_symbols_name ON code_symbols(symbol_name);

            CREATE VIRTUAL TABLE IF NOT EXISTS file_chunks_fts USING fts5(
                file_path,
                content,
                content='file_chunks',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS file_chunks_ai AFTER INSERT ON file_chunks BEGIN
                INSERT INTO file_chunks_fts(rowid, file_path, content)
                VALUES (new.id, new.file_path, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS file_chunks_ad AFTER DELETE ON file_chunks BEGIN
                INSERT INTO file_chunks_fts(file_chunks_fts, rowid, file_path, content)
                VALUES ('delete', old.id, old.file_path, old.content);
            END;
        """)
        conn.commit()

    def _reindex_workspace(self) -> None:
        """Scan workspace and populate FTS5 index with clean code blocks."""
        logger.info("Scanning workspace to build RAG index...")
        conn = self._get_conn()

        # Clear previous chunks and symbols
        conn.executescript("""
            DELETE FROM file_chunks_fts;
            DELETE FROM file_chunks;
            DELETE FROM code_symbols;
        """)
        conn.commit()

        exclude_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist", ".nexus-agent"}
        exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".pyc"}

        # Regex symbol patterns
        py_class_pat = re.compile(r'^\s*class\s+(\w+)')
        py_def_pat = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)')
        js_class_pat = re.compile(r'^\s*class\s+(\w+)')
        js_func_pat = re.compile(r'^\s*(?:async\s+)?function\s+(\w+)')

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in exclude_extensions:
                    continue

                try:
                    # Size protection threshold: skip files larger than 5MB
                    if file_path.stat().st_size > 5 * 1024 * 1024:
                        continue

                    rel_path = file_path.relative_to(self.workspace)
                    content = file_path.read_text(encoding="utf-8", errors="ignore")

                    # Split files into chunks of ~1000 chars with 100 overlap
                    lines = content.splitlines()
                    # Minified code detection: skip if any line exceeds 2000 characters
                    if any(len(line) > 2000 for line in lines):
                        continue

                    # Extract code symbols
                    # Batch collect symbols and chunks for executemany
                    symbol_data = []
                    chunk_data = []

                    file_suffix = file_path.suffix.lower()
                    is_python = file_suffix == ".py"
                    is_js_ts = file_suffix in (".js", ".ts", ".jsx", ".tsx")

                    if is_python or is_js_ts:
                        for idx, line in enumerate(lines):
                            line_num = idx + 1
                            symbol_name = None
                            symbol_type = None

                            if is_python:
                                # Python rules
                                class_match = py_class_pat.match(line)
                                if class_match:
                                    symbol_name = class_match.group(1)
                                    symbol_type = "class"
                                else:
                                    def_match = py_def_pat.match(line)
                                    if def_match:
                                        symbol_name = def_match.group(1)
                                        symbol_type = "function"

                            elif is_js_ts:
                                # JS/TS rules
                                class_match = js_class_pat.match(line)
                                if class_match:
                                    symbol_name = class_match.group(1)
                                    symbol_type = "class"
                                else:
                                    func_match = js_func_pat.match(line)
                                    if func_match:
                                        symbol_name = func_match.group(1)
                                        symbol_type = "function"

                            if symbol_name and symbol_type:
                                symbol_data.append((str(rel_path), symbol_name, symbol_type, line_num, line_num + 5))

                    chunk_lines_size = 35
                    overlap_lines_size = 5

                    i = 0
                    while i < len(lines):
                        chunk_lines = lines[i : i + chunk_lines_size]
                        chunk_text = "\n".join(chunk_lines)

                        if chunk_text.strip():
                            chunk_data.append((str(rel_path), chunk_text, i + 1, i + len(chunk_lines)))

                        i += (chunk_lines_size - overlap_lines_size)

                    # Batch insert symbols and chunks
                    if symbol_data:
                        conn.executemany(
                            "INSERT INTO code_symbols (file_path, symbol_name, symbol_type, start_line, end_line) "
                            "VALUES (?, ?, ?, ?, ?)",
                            symbol_data
                        )
                    if chunk_data:
                        conn.executemany(
                            "INSERT INTO file_chunks (file_path, content, start_line, end_line) "
                            "VALUES (?, ?, ?, ?)",
                            chunk_data
                        )
                except (OSError, ValueError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to index file {file_path}: {e}")

        conn.commit()
        logger.info("RAG Index generated successfully!")

    def execute(self, query: str, reindex: bool = False, max_results: int = 5) -> str:
        """Run query against RAG index."""
        # Limit query length to prevent injection / DoS
        if len(query) > 256:
            return "Error: Query exceeds maximum length of 256 characters."

        conn = self._get_conn()

        # Check if RAG db is empty
        cursor = conn.execute("SELECT COUNT(*) as count FROM file_chunks")
        if cursor.fetchone()["count"] == 0 or reindex:
            self._reindex_workspace()

        # Gather hybrid RAG results
        results_map = {}

        # 1. Symbol Match Boost (Hybrid Retrieval)
        try:
            # Check exact or partial symbol matches
            symbol_cursor = conn.execute(
                "SELECT * FROM code_symbols WHERE symbol_name LIKE ? LIMIT ?",
                (f"%{query}%", max_results)
            )
            for sym in symbol_cursor:
                # Find matching chunk that contains this symbol's start line
                chunk_cursor = conn.execute(
                    "SELECT * FROM file_chunks WHERE file_path = ? AND start_line <= ? AND end_line >= ?",
                    (sym["file_path"], sym["start_line"], sym["start_line"])
                )
                for chunk in chunk_cursor:
                    c = dict(chunk)
                    key = (c["file_path"], c["start_line"])
                    c["symbol_boost"] = True
                    c["symbol_info"] = f"[{sym['symbol_type'].upper()}: {sym['symbol_name']}]"
                    results_map[key] = c
        except (ValueError, OSError) as e:
            logger.debug(f"Symbol retrieval failed: {e}")

        # 2. Standard FTS5 Keyword Match
        # Safe and clean escaping of MATCH query parameters to prevent FTS5 parsing injection
        clean_words = []
        for word in query.split():
            clean_word = word.replace('"', '""').replace("'", "''")
            if not clean_word.isalnum():
                clean_word = f'"{clean_word}"'
            clean_words.append(clean_word)
        safe_query = " ".join(clean_words)
        try:
            cursor = conn.execute(
                """
                SELECT fts.rowid, m.*, rank
                FROM file_chunks_fts fts
                JOIN file_chunks m ON m.id = fts.rowid
                WHERE file_chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, max_results),
            )
            for row in cursor:
                r = dict(row)
                key = (r["file_path"], r["start_line"])
                if key not in results_map:
                    r["symbol_boost"] = False
                    r["symbol_info"] = ""
                    results_map[key] = r
        except sqlite3.OperationalError:
            # Fallback to standard LIKE (escape wildcards to prevent injection)
            escaped = query.replace("%", r"\%").replace("_", r"\_")
            like_query = f"%{escaped}%"
            cursor = conn.execute(
                "SELECT *, 0 as rank FROM file_chunks WHERE content LIKE ? ESCAPE '\\' LIMIT ?",
                (like_query, max_results),
            )
            for row in cursor:
                r = dict(row)
                key = (r["file_path"], r["start_line"])
                if key not in results_map:
                    r["symbol_boost"] = False
                    r["symbol_info"] = ""
                    results_map[key] = r

        # Format retrieved chunks (limit to max_results)
        results = []
        sorted_chunks = sorted(
            results_map.values(),
            key=lambda x: (not x.get("symbol_boost", False), x.get("rank", 0))
        )[:max_results]

        for r in sorted_chunks:
            boost_header = f" {r['symbol_info']}" if r.get("symbol_info") else ""
            results.append(
                f"### File: {r['file_path']} (Lines {r['start_line']}-{r['end_line']}){boost_header}\n"
                f"```\n{r['content']}\n```\n"
            )

        if not results:
            return f"No relevant workspace matches found for query: '{query}'."

        return (
            f"Found {len(results)} relevant file code blocks in the workspace:\n\n" +
            "\n".join(results)
        )

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """Close database connection to release Windows file locks."""
        if self._conn:
            self._conn.close()
            self._conn = None
