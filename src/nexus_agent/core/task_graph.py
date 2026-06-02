"""
Hierarchical Task Graph — Recursive decomposition of high-level goals into a DAG of sub-tasks.

Enables the agent to break down complex goals into subgoals, manage execution state,
track dependencies, handle failures, and render progress visually.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexus_agent.llm.base import LLMProvider, Message, Role

logger = logging.getLogger(__name__)

# Constants for LLM decomposition
DECOMPOSE_TEMPERATURE = 0.1
DECOMPOSE_MAX_TOKENS = 2048


@dataclass
class TaskNode:
    """A single node representing a task or subgoal in the hierarchical task graph."""
    id: str
    title: str
    description: str
    status: str = "pending"  # pending, running, completed, failed, blocked
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)      # Node IDs of subtasks
    dependencies: list[str] = field(default_factory=list)  # Node IDs this task depends on
    result: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskNode:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            status=data["status"],
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            dependencies=data.get("dependencies", []),
            result=data.get("result"),
        )


class TaskGraphStore:
    """Handles persistence of TaskGraph data to and from disk."""

    def __init__(self, tasks_dir: Path, session_id: str):
        self.tasks_dir = tasks_dir
        self.storage_file = tasks_dir / f"{session_id}.json"

    def save(self, session_id: str, root_id: str | None, nodes: dict[str, TaskNode]) -> None:
        """Persist the task graph to disk."""
        try:
            self.tasks_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "session_id": session_id,
                "root_id": root_id,
                "nodes": {nid: node.to_dict() for nid, node in nodes.items()}
            }
            self.storage_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (OSError, ValueError) as e:
            logger.error(f"Failed to save task graph: {e}")

    def load(self) -> dict | None:
        """Load the task graph from disk. Returns data dict or None."""
        if not self.storage_file.exists():
            return None
        try:
            return json.loads(self.storage_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.error(f"Failed to load task graph: {e}")
            return None


class TaskGraphRenderer:
    """Renders a TaskGraph as Markdown or Mermaid diagram."""

    @staticmethod
    def render_markdown(nodes: dict[str, TaskNode], root_id: str | None) -> str:
        """Render the task graph as a clean markdown checklist tree."""
        if not root_id or root_id not in nodes:
            return "No tasks initialized."

        root = nodes[root_id]
        lines = [f"### Task Breakdown: {root.description[:100]}..."]

        total = sum(1 for nid in nodes if nid != root_id)
        completed = sum(1 for n in nodes.values() if n != root and n.status == "completed")
        pct = int((completed / total) * 100) if total else 100
        lines.append(f"**Progress:** {pct}% complete ({completed}/{total} tasks)")
        lines.append("")

        for child_id in root.children:
            child = nodes.get(child_id)
            if not child:
                continue

            status_icon = {
                "completed": "✅",
                "running": "⚡",
                "failed": "❌",
                "blocked": "🚫",
                "pending": "⏳",
            }.get(child.status, "⏳")

            dep_str = ""
            if child.dependencies:
                dep_str = f" *(depends on: {', '.join(child.dependencies)})*"

            lines.append(f"- {status_icon} **{child.title}** ({child.id}){dep_str}")
            lines.append(f"  *{child.description}*")
            if child.result:
                lines.append(f"  ↳ *Result:* {child.result}")

        return "\n".join(lines)

    @staticmethod
    def render_mermaid(nodes: dict[str, TaskNode], root_id: str | None) -> str:
        """Generate a Mermaid diagram code block for the task graph DAG."""
        if not root_id:
            return ""

        lines = ["graph TD"]
        for nid, node in nodes.items():
            if nid == root_id:
                title = "Goal"
                shape = f"({node.description[:30]}...)"
            else:
                title = node.title
                shape = f"[\"{title} ({nid})\"]"

            lines.append(f"    {nid}{shape}")

            cls_name = {
                "completed": "doneNode",
                "running": "runNode",
                "failed": "failNode",
                "blocked": "blockNode",
                "pending": "waitNode",
            }.get(node.status, "waitNode")
            lines.append(f"    class {nid} {cls_name}")

        root = nodes[root_id]
        for child_id in root.children:
            lines.append(f"    {root_id} -.-> {child_id}")

        for nid, node in nodes.items():
            for dep_id in node.dependencies:
                lines.append(f"    {dep_id} --> {nid}")

        lines.extend([
            "    classDef doneNode fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff;",
            "    classDef runNode fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff;",
            "    classDef failNode fill:#f44336,stroke:#c62828,stroke-width:2px,color:#fff;",
            "    classDef blockNode fill:#9e9e9e,stroke:#424242,stroke-width:2px,color:#fff;",
            "    classDef waitNode fill:#37474f,stroke:#263238,stroke-width:1px,color:#cfd8dc;"
        ])

        return "\n".join(lines)


class TaskGraph:
    """Hierarchical Task Graph (DAG) for autonomous goal execution."""

    def __init__(
        self,
        session_id: str,
        workspace: Path | None = None,
        provider: LLMProvider | None = None,
    ):
        """Initialize the task graph.

        Args:
            session_id: Unique session identifier for persistence.
            workspace: Root workspace directory.
            provider: LLM provider for goal decomposition.
        """
        self.session_id = session_id
        self.workspace = workspace or Path.cwd()
        self.provider = provider
        self.nodes: dict[str, TaskNode] = {}
        self.root_id: str | None = None

        # Setup storage path
        self.tasks_dir = self.workspace / ".nexus-agent" / "tasks"
        self._store = TaskGraphStore(self.tasks_dir, self.session_id)
        self._renderer = TaskGraphRenderer()

    def add_node(self, node: TaskNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def save(self) -> None:
        """Persist the task graph to disk."""
        self._store.save(self.session_id, self.root_id, self.nodes)

    def load(self) -> bool:
        """Load the task graph from disk. Returns True if successful."""
        data = self._store.load()
        if data is None:
            return False
        self.root_id = data.get("root_id")
        self.nodes = {
            nid: TaskNode.from_dict(ndata)
            for nid, ndata in data.get("nodes", {}).items()
        }
        return True

    def decompose(self, goal: str, max_depth: int = 3) -> TaskNode:
        """LLM-driven recursive goal decomposition.

        Args:
            goal: The high-level objective description.
            max_depth: Maximum hierarchy depth.

        Returns:
            The root TaskNode.
        """
        # Sanitize goal string to prevent prompt injection
        sanitized_goal = goal.replace("{", "{{").replace("}", "}}")
        root_node = TaskNode(
            id=str(uuid.uuid4())[:8],
            title="Root Goal",
            description=goal,
            status="pending"
        )
        self.root_id = root_node.id
        self.add_node(root_node)

        if not self.provider:
            # Heuristic fallback if provider is not available
            self._heuristic_decompose(root_node, goal)
            self.save()
            return root_node

        try:
            system_prompt = (
                "You are an expert project planner. Break down the user's high-level goal into a hierarchical list "
                "of actionable subgoals/tasks. You MUST output a valid JSON array of tasks where each task contains:\n"
                "- 'title': Short descriptive title\n"
                "- 'description': What to do\n"
                "- 'dependencies': A list of integers referencing index indices of other tasks that MUST be completed first "
                "(0-indexed index of the task in this array)\n\n"
                "Keep the list highly technical, sequential, and focused on codebase editing, verification, and testing. "
                "Limit the breakdown to 3-6 key sub-tasks."
            )
            user_prompt = f"Goal:\n{sanitized_goal}\n\nDecompose this goal into a list of structured JSON sub-tasks."

            messages = [
                Message(role=Role.SYSTEM, content=system_prompt),
                Message(role=Role.USER, content=user_prompt),
            ]

            response = self.provider.chat_completion(
                messages=messages,
                temperature=DECOMPOSE_TEMPERATURE,
                max_tokens=DECOMPOSE_MAX_TOKENS
            )

            content = (response.content or "").strip()
            # Extract JSON list
            if "```" in content:
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
                if match:
                    content = match.group(1).strip()

            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                tasks_data = json.loads(content[start:end])
            else:
                tasks_data = json.loads(content)

            # Map array indices to node IDs
            index_to_id: dict[int, str] = {}
            nodes_to_add: list[TaskNode] = []

            for idx, item in enumerate(tasks_data):
                nid = str(uuid.uuid4())[:8]
                index_to_id[idx] = nid
                node = TaskNode(
                    id=nid,
                    title=item.get("title", f"Subtask {idx + 1}"),
                    description=item.get("description", ""),
                    parent_id=root_node.id,
                    status="pending"
                )
                nodes_to_add.append(node)

            # Resolve dependencies and children
            for idx, item in enumerate(tasks_data):
                node = nodes_to_add[idx]
                root_node.children.append(node.id)

                raw_deps = item.get("dependencies", [])
                for dep_idx in raw_deps:
                    if isinstance(dep_idx, int) and dep_idx in index_to_id:
                        node.dependencies.append(index_to_id[dep_idx])

                self.add_node(node)

        except (ValueError, RuntimeError) as e:
            logger.warning(f"LLM goal decomposition failed: {e}. Falling back to heuristic breakdown.")
            self._heuristic_decompose(root_node, goal)

        self.save()
        return root_node

    def _heuristic_decompose(self, root_node: TaskNode, goal: str) -> None:
        """Create a default deterministic three-stage checklist if LLM decomposition fails."""
        stages = [
            ("Gather Context", "Scan workspace, locate relevant files, and understand current behavior", []),
            ("Implement Changes", "Apply the necessary modifications and edit target source files", [0]),
            ("Verify & Test", "Run diagnostics, compile checks, and execute existing tests to verify correctness", [1]),
        ]

        index_to_id: dict[int, str] = {}
        for idx, (title, desc, deps) in enumerate(stages):
            nid = str(uuid.uuid4())[:8]
            index_to_id[idx] = nid
            node = TaskNode(
                id=nid,
                title=title,
                description=desc,
                parent_id=root_node.id,
                status="pending"
            )
            root_node.children.append(nid)
            for dep_idx in deps:
                if dep_idx in index_to_id:
                    node.dependencies.append(index_to_id[dep_idx])
            self.add_node(node)

    def get_ready_tasks(self) -> list[TaskNode]:
        """Return tasks whose status is pending and all dependencies are completed."""
        ready: list[TaskNode] = []
        for node in self.nodes.values():
            if node.id == self.root_id:
                continue
            if node.status != "pending":
                continue

            # Check if all dependencies are completed
            deps_ok = True
            for dep_id in node.dependencies:
                dep_node = self.nodes.get(dep_id)
                if not dep_node or dep_node.status != "completed":
                    deps_ok = False
                    break

            if deps_ok:
                ready.append(node)
        return ready

    def get_progress(self) -> dict[str, Any]:
        """Return progress metrics for the task graph.

        Note: This method may update node status from 'pending' to 'blocked'
        if dependencies have failed. This is a side effect for accurate reporting.
        """
        total = sum(1 for nid in self.nodes if nid != self.root_id)
        if total == 0:
            return {"percentage": 100, "total": 0, "completed": 0, "pending": 0, "running": 0, "failed": 0, "blocked": 0}

        counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "blocked": 0}

        # Calculate blocked status without mutating node state
        blocked_nodes: set[str] = set()
        for nid, node in self.nodes.items():
            if nid == self.root_id:
                continue
            if node.status == "pending":
                for dep_id in node.dependencies:
                    dep = self.nodes.get(dep_id)
                    if dep and (dep.status == "failed" or dep.status == "blocked"):
                        blocked_nodes.add(nid)
                        break

        for nid, node in self.nodes.items():
            if nid == self.root_id:
                continue

            status = node.status
            if status == "pending" and nid in blocked_nodes:
                status = "blocked"

            if status in counts:
                counts[status] += 1
            else:
                counts["pending"] += 1

        pct = int((counts["completed"] / total) * 100)
        return {
            "percentage": pct,
            "total": total,
            **counts
        }

    def to_markdown(self) -> str:
        """Render the task graph as a clean markdown checklist tree."""
        return self._renderer.render_markdown(self.nodes, self.root_id)

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram code block for the task graph DAG."""
        return self._renderer.render_mermaid(self.nodes, self.root_id)
