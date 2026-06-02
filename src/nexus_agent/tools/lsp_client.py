"""
LSP Client Tool — Zero-dependency Code Intelligence & Linter integration.
Provides local static analysis, syntax diagnostics, definitions, and hover info.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class LSPClientTool(Tool):
    """Language Server Protocol proxy and static code linter."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "lsp_query"

    @property
    def description(self) -> str:
        return (
            "Query the local static code analyzer for diagnostics, definition lookups, or hover info. "
            "Supports Python and JS/TS code files. Returns precise line-level syntax issues and structural definitions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "Code intelligence action: 'definition', 'hover', 'diagnostics'",
                "enum": ["definition", "hover", "diagnostics"],
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
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, action: str, file: str, line: int = 1,
                 character: int = 0, **kwargs: Any) -> str:
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

        if action == "diagnostics":
            return self._run_diagnostics(resolved_path, content)

        elif action == "definition":
            return self._find_definition(resolved_path, content, line, character)

        elif action == "hover":
            return self._get_hover_info(resolved_path, content, line)

        return "Invalid action completed."

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

    def _get_hover_info(self, path: Path, content: str, line_num: int) -> str:
        """Retrieve docstrings and hover info for symbols at this line."""
        if path.suffix.lower() != ".py":
            return f"Hover docstrings extraction currently supported on Python. File: {path.name}"

        try:
            tree = ast.parse(content)
            lines = content.splitlines()
            if line_num < 1 or line_num > len(lines):
                return "Line out of bounds."

            target_line = lines[line_num - 1]
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
