"""
Code Intelligence Tools — Dependencies, call graphs, import graphs, and AST rename propagation.

Leverages Python ast engine to parse source code files, map call relationships,
trace import dependencies, and perform atomic symbol rename operations.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class ImportGraphTool(Tool):
    """Parses source files in the workspace to construct an import dependency graph."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "import_graph"

    @property
    def description(self) -> str:
        return (
            "Analyze codebase import statements and trace module dependencies. "
            "Helps determine which files import a target module."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "The action to take: 'build' (generate full graph) or 'find_dependents' (find files depending on target)",
            },
            "target": {
                "type": "string",
                "description": "Module name or file path to check dependents of (required if action='find_dependents')",
                "required": False,
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["action"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, action: str, target: str = "", **kwargs: Any) -> str:
        graph = self._build_import_graph()

        if action == "build":
            if not graph:
                return "No imports detected in the workspace."
            lines = ["### Workspace Import Graph (Module Adjacency List)"]
            for mod, imports in graph.items():
                if imports:
                    lines.append(f"- `{mod}` imports: {', '.join(f'`{i}`' for i in imports)}")
            return "\n".join(lines)

        elif action == "find_dependents":
            if not target:
                return "Error: 'target' parameter is required to find dependents."

            target_norm = target.replace("/", ".").replace("\\", ".").replace(".py", "")
            dependents = []

            for mod, imports in graph.items():
                for imp in imports:
                    if imp == target_norm or imp.startswith(target_norm + "."):
                        dependents.append(mod)

            if not dependents:
                return f"No modules found that import '{target}'."
            return f"### Modules importing '{target}':\n" + "\n".join(f"- `{d}`" for d in dependents)

        return f"Unknown action: '{action}'."

    def _build_import_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}
        exclude_dirs = {".git", ".venv", "node_modules", "__pycache__", ".nexus-agent"}

        try:
            for root, dirs, files in os.walk(str(self.workspace)):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                for file in files:
                    if file.endswith(".py"):
                        file_path = Path(root) / file
                        rel_path = file_path.relative_to(self.workspace)
                        mod_name = ".".join(rel_path.with_suffix("").parts)

                        imports = set()
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            try:
                                tree = ast.parse(content)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.Import):
                                        for alias in node.names:
                                            imports.add(alias.name.split(".")[0].split(" as ")[0])
                                    elif isinstance(node, ast.ImportFrom):
                                        if node.module:
                                            imports.add(node.module.split(".")[0])
                            except SyntaxError:
                                pass
                        except (OSError, UnicodeDecodeError, ValueError):
                            logger.debug("Failed to parse imports in %s", file_path)

                        graph[mod_name] = imports
        except (OSError, ValueError) as e:
            logger.error(f"Error building import graph: {e}")

        return graph


class CallGraphTool(Tool):
    """AST-based caller-callee static call graph generator for Python files."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "call_graph"

    @property
    def description(self) -> str:
        return "Generates a call-graph for Python functions inside a file or traces where a function is called."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "Relative path to target Python file to map call graphs inside",
            },
            "trace_function": {
                "type": "string",
                "description": "Function name to search usages of across this file",
                "required": False,
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["file_path"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    def execute(self, file_path: str, trace_function: str = "", **kwargs: Any) -> str:
        try:
            target = self.resolve_workspace_path(self.workspace, file_path)
        except ValueError as e:
            return f"Error: {e}"
        if not target.exists():
            return f"Error: File '{file_path}' does not exist."

        try:
            tree = ast.parse(target.read_text(encoding="utf-8"))
        except (SyntaxError, OSError, ValueError, UnicodeDecodeError) as e:
            return f"AST Parsing Error for file '{file_path}': {e}"

        call_map = self._build_call_graph(tree)

        if trace_function:
            # Trace calls to this function
            callers = []
            for caller, callees in call_map.items():
                if trace_function in callees:
                    callers.append(caller)

            if not callers:
                return f"No function calls targeting '{trace_function}' detected inside `{file_path}`."
            return f"### Function '{trace_function}' is called by:\n" + "\n".join(f"- `{c}`" for c in callers)

        else:
            # Return call map
            lines = [f"### Static Call Graph for `{file_path}`"]
            for caller, callees in call_map.items():
                if callees:
                    lines.append(f"- `{caller}` calls: {', '.join(f'`{c}`' for c in sorted(callees))}")
            return "\n".join(lines)

    def _build_call_graph(self, tree: ast.AST) -> dict[str, set[str]]:
        call_map: dict[str, set[str]] = {}
        current_func = "global"

        class CallVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                nonlocal current_func
                old_func = current_func
                current_func = node.name
                call_map[current_func] = set()
                self.generic_visit(node)
                current_func = old_func

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                nonlocal current_func
                old_func = current_func
                current_func = node.name
                call_map[current_func] = set()
                self.generic_visit(node)
                current_func = old_func

            def visit_Call(self, node: ast.Call):
                # Retrieve call name
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr

                if name:
                    if current_func not in call_map:
                        call_map[current_func] = set()
                    call_map[current_func].add(name)
                self.generic_visit(node)

        CallVisitor().visit(tree)
        return call_map


class RenameTool(Tool):
    """AST-based batch renaming tool for variables, functions, and modules across scope."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "rename_symbol"

    @property
    def description(self) -> str:
        return "AST-based find-and-replace to safely rename symbols/variables across scope in a file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "Relative path to target Python file",
            },
            "old_symbol": {
                "type": "string",
                "description": "Symbol name to replace",
            },
            "new_symbol": {
                "type": "string",
                "description": "New replacement symbol name",
            }
        }

    @property
    def required_params(self) -> list[str]:
        return ["file_path", "old_symbol", "new_symbol"]

    @property
    def permission_level(self) -> str:
        return "read-write"

    _MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def execute(self, file_path: str, old_symbol: str, new_symbol: str, **kwargs: Any) -> str:
        try:
            target = self.resolve_workspace_path(self.workspace, file_path)
        except ValueError as e:
            return f"Error: {e}"
        if not target.exists():
            return f"Error: File '{file_path}' does not exist."

        # Max file size check
        try:
            if target.stat().st_size > self._MAX_FILE_SIZE:
                return f"Error: File too large for rename ({target.stat().st_size / 1024 / 1024:.1f}MB > 10MB)."
        except OSError as e:
            return f"Error: Cannot stat file: {e}"

        try:
            source = target.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError, ValueError, UnicodeDecodeError) as e:
            return f"AST error: {e}"

        # Refactor symbol usages in names or arguments
        modified = False
        replacements = 0

        class RenameTransformer(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name):
                nonlocal modified, replacements
                if node.id == old_symbol:
                    node.id = new_symbol
                    modified = True
                    replacements += 1
                return self.generic_visit(node)

            def visit_FunctionDef(self, node: ast.FunctionDef):
                nonlocal modified, replacements
                if node.name == old_symbol:
                    node.name = new_symbol
                    modified = True
                    replacements += 1
                return self.generic_visit(node)

            def visit_arg(self, node: ast.arg):
                nonlocal modified, replacements
                if node.arg == old_symbol:
                    node.arg = new_symbol
                    modified = True
                    replacements += 1
                return self.generic_visit(node)

        transformer = RenameTransformer()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        if not modified:
            return f"No occurrences of symbol '{old_symbol}' found inside '{file_path}'."

        try:
            new_source = ast.unparse(new_tree)
            # Write to temp file first, validate, then atomic rename
            fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".py.tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    tmp.write(new_source)
                # Validate the temp file parses correctly
                with open(tmp_path, encoding="utf-8") as f:
                    ast.parse(f.read())
            except (SyntaxError, OSError, ValueError, UnicodeDecodeError):
                os.unlink(tmp_path)
                raise

            # Create .bak snapshot before overwriting
            bak_path = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, bak_path)

            # Atomic rename
            os.replace(tmp_path, str(target))
            return f"Successfully renamed '{old_symbol}' to '{new_symbol}' ({replacements} replacements) in `{file_path}`."
        except (SyntaxError, OSError, ValueError, UnicodeDecodeError) as e:
            # fallback to simple regex rename if ast unparse has quirks or is python version specific
            try:
                pattern = r'\b' + re.escape(old_symbol) + r'\b'
                count = 0
                lines = []
                for line in source.splitlines():
                    new_line, num = re.subn(pattern, new_symbol, line)
                    count += num
                    lines.append(new_line)

                # Also use temp file for regex fallback
                fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".py.tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                        tmp.write("\n".join(lines) + "\n")
                except (OSError, ValueError, UnicodeEncodeError):
                    os.unlink(tmp_path)
                    raise

                bak_path = target.with_suffix(target.suffix + ".bak")
                if not bak_path.exists():
                    shutil.copy2(target, bak_path)

                os.replace(tmp_path, str(target))
                return f"Successfully updated symbol '{old_symbol}' to '{new_symbol}' ({count} regex replacements) in `{file_path}`."
            except (OSError, ValueError, UnicodeEncodeError) as re_err:
                return f"Failed to rewrite file content: {re_err} (AST error: {e})"
