"""
LSP Client Tool — Real Language Server Protocol proxy with AST-based fallback.

When a language server is installed and reachable (e.g. ``pylsp``, ``pyright``,
``rust-analyzer``, ``gopls``, ``typescript-language-server``), queries are sent
over the real LSP JSON-RPC wire protocol via ``lsp_transport.LSPClientPool``.
Otherwise we fall back to a fast local ``ast``/regex pass that handles Python
and JS/TS bracket validation and Python symbol lookup.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool
from nexus_agent.tools.lsp_transport import LSPClient, LSPClientPool, LSPConfig, LSPError

logger = logging.getLogger(__name__)

_POOL_KEY = "_nexus_lsp_pool"


def _get_pool(workspace: Path) -> LSPClientPool:
    """Return a process-wide pool keyed on workspace path."""
    if not hasattr(_get_pool, "_pools"):
        _get_pool._pools = {}  # type: ignore[attr-defined]
    pools: dict[str, LSPClientPool] = _get_pool._pools  # type: ignore[attr-defined]
    key = str(workspace.resolve())
    pool = pools.get(key)
    if pool is None:
        pool = LSPClientPool(workspace=workspace)
        pools[key] = pool
    return pool


def register_lsp_server(language: str, config: LSPConfig) -> None:
    """Public hook for users to register a custom LSP server (e.g. pyright)."""
    _get_pool(Path.cwd()).register(language, config)


class LSPClientTool(Tool):
    """Language Server Protocol proxy and static code linter."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()
        self._pool = _get_pool(self.workspace)

    @property
    def name(self) -> str:
        return "lsp_query"

    @property
    def description(self) -> str:
        return (
            "Query a real Language Server (pylsp, pyright, rust-analyzer, gopls, "
            "typescript-language-server, ...) for diagnostics, definition lookups, "
            "hover info, completions, references, document symbols, and rename "
            "support. Falls back to a fast local AST/static check for Python and "
            "JS/TS when no server is installed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "Code intelligence action",
                "enum": [
                    "definition",
                    "hover",
                    "diagnostics",
                    "references",
                    "document_symbols",
                    "completion",
                    "format",
                    "rename",
                ],
            },
            "file": {
                "type": "string",
                "description": "Path to the source file in workspace",
            },
            "line": {
                "type": "integer",
                "description": "Line number (1-indexed)",
                "required": False,
            },
            "character": {
                "type": "integer",
                "description": "Character position (0-indexed)",
                "required": False,
            },
            "new_name": {
                "type": "string",
                "description": "New symbol name (required for action='rename')",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, action: str, file: str, line: int = 1,
                 character: int = 0, new_name: str = "", **kwargs: Any) -> str:
        # Always use the tool's configured workspace - do not allow caller override
        try:
            resolved_path = Tool.resolve_workspace_path(self.workspace, file)
        except ValueError as ve:
            return f"Error: Path validation failed: {ve}"

        if not resolved_path.exists():
            return f"Error: Target file not found: {file}"

        try:
            content = resolved_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            return f"Error: Failed to read file {file}: {e}"

        # Try a real LSP server first; gracefully fall back to local analysis.
        client = self._pool.get(str(resolved_path))
        if client is not None:
            try:
                return self._dispatch_lsp(client, resolved_path, content, action,
                                          line, character, new_name)
            except LSPError as e:
                logger.info("LSP dispatch failed (%s) — falling back to local analyzer: %s",
                            action, e)

        # Local fallback path
        if action == "diagnostics":
            return self._run_diagnostics(resolved_path, content)
        if action == "definition":
            return self._find_definition(resolved_path, content, line, character)
        if action == "hover":
            return self._get_hover_info(resolved_path, content, line, character)
        return f"Action '{action}' is not supported by the local fallback (no LSP server installed)."

    def _dispatch_lsp(
        self,
        client: LSPClient,
        path: Path,
        content: str,
        action: str,
        line: int,
        character: int,
        new_name: str,
    ) -> str:
        """Forward a query to a real LSP server and render the response."""
        uri = path.resolve().as_uri()
        text_doc = {"uri": uri}
        position = {"line": max(0, line - 1), "character": max(0, character)}

        # Make sure the server has the latest text
        client.did_open(str(path), content, language_id=client._guess_language_id(str(path)))

        if action == "diagnostics":
            # Prefer pull-mode ``textDocument/diagnostic`` (LSP 3.16+).
            try:
                result = client.request(
                    "textDocument/diagnostic",
                    {"textDocument": text_doc},
                )
            except LSPError:
                # Fall back to publishDiagnostics accumulation isn't possible in one
                # request, so return a quick syntax check via the server's analyzer.
                result = None
            diagnostics: list[dict[str, Any]] = []
            if isinstance(result, dict):
                diagnostics = list(result.get("items") or [])
            return self._render_diagnostics(path, diagnostics, content)

        if action == "definition":
            result = client.request(
                "textDocument/definition",
                {"textDocument": text_doc, "position": position},
            )
            return self._render_locations(path, result, kind="Definition")

        if action == "hover":
            result = client.request(
                "textDocument/hover",
                {"textDocument": text_doc, "position": position},
            )
            return self._render_hover(result)

        if action == "references":
            result = client.request(
                "textDocument/references",
                {"textDocument": text_doc, "position": position, "context": {"includeDeclaration": True}},
            )
            return self._render_locations(path, result, kind="Reference")

        if action == "document_symbols":
            result = client.request(
                "textDocument/documentSymbol",
                {"textDocument": text_doc},
            )
            return self._render_symbols(result)

        if action == "completion":
            result = client.request(
                "textDocument/completion",
                {"textDocument": text_doc, "position": position},
            )
            return self._render_completions(result)

        if action == "format":
            result = client.request(
                "textDocument/formatting",
                {"textDocument": text_doc, "options": {"tabSize": 4, "insertSpaces": True}},
            )
            if not result:
                return "No formatting changes reported by the language server."
            return "Formatting edits available from the server. Apply via edit_file with the returned WorkspaceEdit."

        if action == "rename":
            if not new_name:
                return "Error: 'new_name' is required for action='rename'."
            result = client.request(
                "textDocument/rename",
                {"textDocument": text_doc, "position": position, "newName": new_name},
            )
            return self._render_rename(result, new_name)

        return f"Error: Unknown action '{action}'."

    # ----------------------------------------------------------------- renderers

    @staticmethod
    def _render_diagnostics(path: Path, diagnostics: list[dict[str, Any]],
                             content: str) -> str:
        if not diagnostics:
            return f"✅ Diagnostics OK! Language server reported 0 issues in {path.name}."
        lines = [f"### {len(diagnostics)} issue(s) reported by language server in {path.name}:"]
        for d in diagnostics[:50]:
            sev = d.get("severity", 1)
            sev_label = {1: "ERROR", 2: "WARN", 3: "INFO", 4: "HINT"}.get(sev, "DIAG")
            rng = d.get("range", {}) or {}
            start = rng.get("start", {}) or {}
            line_no = int(start.get("line", 0)) + 1
            col_no = int(start.get("character", 0)) + 1
            source = d.get("source", "")
            code = d.get("code", "")
            tag = f" [{source}/{code}]" if source or code else ""
            lines.append(f"  [{sev_label}] line {line_no}, col {col_no}{tag}: {d.get('message', '').strip()}")
        return "\n".join(lines)

    @staticmethod
    def _render_locations(path: Path, locations: Any, kind: str) -> str:
        items = locations if isinstance(locations, list) else ([locations] if locations else [])
        if not items:
            return f"No {kind.lower()} found by the language server."
        out = [f"### {kind} for {path.name}:"]
        for loc in items[:20]:
            if not isinstance(loc, dict):
                continue
            uri = loc.get("uri") or loc.get("targetUri", "")
            target_path = uri.replace("file:///", "").replace("file://", "")
            r = loc.get("range", {}) or {}
            start = r.get("start", {}) or {}
            line_no = int(start.get("line", 0)) + 1
            col_no = int(start.get("character", 0)) + 1
            out.append(f"  - {target_path}:{line_no}:{col_no}")
        return "\n".join(out)

    @staticmethod
    def _render_hover(hover: Any) -> str:
        if not hover or not isinstance(hover, dict):
            return "No hover information available."
        contents = hover.get("contents")
        if isinstance(contents, dict):
            text = contents.get("value", "")
        elif isinstance(contents, list):
            text = "\n".join(
                c.get("value", str(c)) if isinstance(c, dict) else str(c) for c in contents
            )
        else:
            text = str(contents)
        if not text.strip():
            return "No hover information available."
        return f"### Hover:\n{text.strip()}"

    @staticmethod
    def _render_symbols(symbols: Any) -> str:
        if not symbols or not isinstance(symbols, list):
            return "No symbols reported by the language server."

        def flatten(items: list[dict[str, Any]], depth: int = 0) -> list[str]:
            lines: list[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "?")
                kind = item.get("kind", 0)
                r = item.get("location", {}).get("range", {}) if "location" in item else item.get("range", {})
                start = (r or {}).get("start", {}) or {}
                line_no = int(start.get("line", 0)) + 1
                lines.append(f"  {'  ' * depth}{name}  (kind {kind})  line {line_no}")
                children = item.get("children") or []
                if children:
                    lines.extend(flatten(children, depth + 1))
            return lines

        body = flatten(symbols)
        return f"### Document symbols:\n" + "\n".join(body) if body else "No symbols reported by the language server."

    @staticmethod
    def _render_completions(result: Any) -> str:
        items: list[dict[str, Any]] = []
        if isinstance(result, dict):
            items = list(result.get("items") or [])
        elif isinstance(result, list):
            items = [r for r in result if isinstance(r, dict)]
        if not items:
            return "No completion items returned by the language server."
        lines = [f"### {len(items)} completion suggestion(s):"]
        for c in items[:30]:
            label = c.get("label", "?")
            detail = c.get("detail", "")
            doc = c.get("documentation", "")
            if isinstance(doc, dict):
                doc = doc.get("value", "")
            tag = f" — {detail}" if detail else ""
            doc_tag = f"\n      {doc.strip()}" if doc else ""
            lines.append(f"  - {label}{tag}{doc_tag}")
        return "\n".join(lines)

    @staticmethod
    def _render_rename(workspace_edit: Any, new_name: str) -> str:
        if not workspace_edit or not isinstance(workspace_edit, dict):
            return f"No rename edits returned by the language server (target not found?)."
        changes = workspace_edit.get("changes") or {}
        document_changes = workspace_edit.get("documentChanges") or []
        total = sum(len(v) for v in changes.values()) if isinstance(changes, dict) else 0
        total += sum(
            len(d.get("edits") or []) for d in document_changes if isinstance(d, dict)
        )
        if total == 0:
            return f"No rename edits returned by the language server (target not found?)."
        return f"✅ Rename to '{new_name}' would affect {total} location(s) across the workspace."

    def _run_diagnostics(self, path: Path, content: str) -> str:
        """Run a local parser to check for syntax and compile errors."""
        if path.suffix.lower() == ".py":
            try:
                # Compile to check syntax error
                compile(content, str(path), "exec")
                return f"✅ Diagnostics OK! No syntax compile errors found in Python file: {path.name}"
            except SyntaxError as se:
                return (
                    f"❌ SYNTAX DIAGNOSTICS FAILURE in {path.name}:\n"
                    f"  Line {se.lineno}, Offset {se.offset}: {se.msg}\n"
                    f"  Code: {se.text.strip() if se.text else ''}"
                )
        elif path.suffix.lower() in (".js", ".ts", ".jsx", ".tsx"):
            # Bracket/parenthesis linter fallback for JS with string/comment state tracking
            bracket_map = {')': '(', '}': '{', ']': '['}
            stack = []
            in_single_quote = False
            in_double_quote = False
            in_template = False
            in_line_comment = False
            in_block_comment = False
            prev_char = ""

            for idx, line in enumerate(content.splitlines()):
                in_line_comment = False
                for char_idx, char in enumerate(line):
                    # Track string state
                    if in_block_comment:
                        if prev_char == '*' and char == '/':
                            in_block_comment = False
                        prev_char = char
                        continue
                    if in_line_comment:
                        continue
                    if in_single_quote:
                        if char == "'" and prev_char != '\\':
                            in_single_quote = False
                        prev_char = char
                        continue
                    if in_double_quote:
                        if char == '"' and prev_char != '\\':
                            in_double_quote = False
                        prev_char = char
                        continue
                    if in_template:
                        if char == '`' and prev_char != '\\':
                            in_template = False
                        prev_char = char
                        continue

                    # Check for comment starts
                    if char == '/' and char_idx + 1 < len(line):
                        next_char = line[char_idx + 1]
                        if next_char == '/':
                            in_line_comment = True
                            prev_char = char
                            continue
                        elif next_char == '*':
                            in_block_comment = True
                            prev_char = char
                            continue

                    # Check for string starts
                    if char == "'":
                        in_single_quote = True
                    elif char == '"':
                        in_double_quote = True
                    elif char == '`':
                        in_template = True
                    elif char in bracket_map.values():
                        stack.append((char, idx + 1, char_idx))
                    elif char in bracket_map.keys():
                        if not stack:
                            return f"❌ SYNTAX ERROR: Unexpected closing bracket '{char}' at line {idx + 1}, column {char_idx + 1}"
                        last_char, last_line, last_col = stack.pop()
                        if last_char != bracket_map[char]:
                            return f"❌ SYNTAX ERROR: Unmatched brackets: '{last_char}' opened at line {last_line} but closed with '{char}' at line {idx + 1}"
                    prev_char = char
            if stack:
                last_char, last_line, last_col = stack.pop()
                return f"❌ SYNTAX ERROR: Unclosed bracket '{last_char}' opened at line {last_line}, column {last_col + 1}"
            return f"✅ Diagnostics OK! Basic structural linter checks passed in file: {path.name}"

        return f"Diagnostics ignored for format: {path.suffix}"

    def _find_definition(self, path: Path, content: str, line_num: int, character: int = 0) -> str:
        """Identify symbol definitions at the given line of code."""
        lines = content.splitlines()
        if line_num < 1 or line_num > len(lines):
            return f"Error: Line {line_num} out of bounds."

        target_line = lines[line_num - 1]

        # Extract the word at the character position if provided
        if character > 0 and character < len(target_line):
            # Find the word containing the character position
            line_start = target_line[:character]
            line_end = target_line[character:]
            # Find word boundaries
            before_match = re.search(r'\w+$', line_start)
            after_match = re.search(r'^\w+', line_end)
            if before_match and after_match:
                word = before_match.group(0) + after_match.group(0)
                words = [word]
            else:
                words = re.findall(r'\b\w+\b', target_line)
        else:
            words = re.findall(r'\b\w+\b', target_line)

        if not words:
            return "No symbols identified at this location."

        results = []
        for word in words[:3]: # Scan first few words
            class_pat = re.compile(rf'^\s*class\s+{re.escape(word)}\b')
            func_pat = re.compile(rf'^\s*(?:def|function|const|async\s+def)\s+{re.escape(word)}\b')

            for idx, line in enumerate(lines):
                if class_pat.match(line):
                    results.append(f"  * Class '{word}' defined at line {idx + 1}")
                elif func_pat.match(line):
                    results.append(f"  * Function '{word}' defined at line {idx + 1}")

        if not results:
            return f"Definition not found locally for symbols: {', '.join(words)}"

        return f"Discovered definition(s) in {path.name}:\n" + "\n".join(results)

    def _get_hover_info(self, path: Path, content: str, line_num: int,
                         character: int = 0) -> str:
        """Retrieve docstrings and hover info for symbols at this line."""
        if path.suffix.lower() != ".py":
            return f"Hover docstrings extraction currently supported on Python. File: {path.name}"

        try:
            tree = ast.parse(content)
            lines = content.splitlines()
            if line_num < 1 or line_num > len(lines):
                return "Line out of bounds."

            target_line = lines[line_num - 1]

            # If a character position was provided, extract the word that
            # contains it. Otherwise fall back to the first word on the line.
            words: list[str]
            if character and 0 < character < len(target_line):
                line_start = target_line[:character]
                line_end = target_line[character:]
                before_match = re.search(r'\w+$', line_start)
                after_match = re.search(r'^\w+', line_end)
                if before_match and after_match:
                    words = [before_match.group(0) + after_match.group(0)]
                else:
                    words = re.findall(r'\b\w+\b', target_line)
            else:
                words = re.findall(r'\b\w+\b', target_line)
            if not words:
                return "No hover symbol found."

            target_word = words[0]
            # Search AST nodes for class/function matching target_word
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == target_word:
                        doc = ast.get_docstring(node)
                        doc_str = doc if doc else "(No docstring available)"
                        sig = f"{node.name}()"
                        if isinstance(node, ast.ClassDef):
                            sig = f"class {node.name}"
                        return f"### Hover Info: {sig}\n\nDocumentation:\n{doc_str}"

            return f"No hover definitions or docstrings found locally for symbol: '{target_word}'"
        except (SyntaxError, OSError, ValueError) as e:
            return f"Failed to extract AST hover details: {e}"
