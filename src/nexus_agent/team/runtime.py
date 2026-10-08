"""Concurrent multi-agent team runtime."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterator

from nexus_agent.agents.registry import AgentRegistry
from nexus_agent.core.agent import AgentEvent, AgentEventType, AgentLoop, AgentLoopConfig, AgentMode
from nexus_agent.llm.base import LLMProvider, Message, Role
from nexus_agent.skills.skill_registry import SkillRegistry
from nexus_agent.storage.layout import StorageLayout

from .models import AgentProfile, TeamAgentState, TeamConfig, TeamMode, TeamRunResult
from .control import register as register_team_control, unregister as unregister_team_control
from .planner import generate_team, infer_mode
from .quality import evaluate_team
from .store import TeamStore
from .tools import TeamReadMessagesTool, TeamSendMessageTool


PermissionCallback = Callable[[Any], bool]
ProviderSelector = Callable[[AgentProfile], LLMProvider]


def build_workspace_tools(
    workspace: Path,
    memory_manager: Any | None = None,
    provider: LLMProvider | None = None,
    agent_loop: Any | None = None,
    include_advanced: bool = True,
    mcp_tools: list[Any] | None = None,
    agent_id: str | None = None,
    team_id: str | None = None,
    session_id: str | None = None,
    research: bool = False,
    research_depth: str = "detailed",
    research_source_strategy: str = "hybrid",
) -> list[Any]:
    from nexus_agent.tools.browser import BrowserTool
    from nexus_agent.tools.boomerang import BoomerangTool
    from nexus_agent.tools.batch_edit import BatchEditTool
    from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
    from nexus_agent.tools.code_intel import CallGraphTool, ImportGraphTool, RenameTool
    from nexus_agent.tools.council import CouncilTool
    from nexus_agent.tools.formal import FormalCheckTool
    from nexus_agent.tools.file_ops import (
        DeleteFileTool,
        ListDirectoryTool,
        MoveFileTool,
        ParseDataTool,
        ReadFileTool,
        RestoreFileTool,
        SearchFilesTool,
        WriteFileTool,
    )
    from nexus_agent.tools.git_ops import CIAnalyzerTool, GitTool, PRGeneratorTool, SmartCommitTool
    from nexus_agent.tools.lsp_client import LSPClientTool
    from nexus_agent.tools.rag_search import RepositoryRAGTool
    from nexus_agent.tools.shell import ShellTool
    from nexus_agent.tools.todowrite import TodoWriteTool
    from nexus_agent.tools.web_search import WebSearchTool
    from nexus_agent.tools.webfetch import WebFetchTool

    tools: list[Any] = [
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        DeleteFileTool(workspace),
        MoveFileTool(workspace),
        RestoreFileTool(workspace),
        ParseDataTool(workspace),
        SearchFilesTool(workspace),
        ListDirectoryTool(workspace),
        ShellTool(workspace),
        CodeEditTool(workspace),
        InsertLinesTool(workspace),
        BatchEditTool(workspace),
        GitTool(workspace),
        SmartCommitTool(workspace, provider),
        PRGeneratorTool(workspace, provider),
        CIAnalyzerTool(provider),
        WebSearchTool(),
        WebFetchTool(),
        BrowserTool(workspace),
        ImportGraphTool(workspace),
        CallGraphTool(workspace),
        RenameTool(workspace),
        LSPClientTool(workspace),
        RepositoryRAGTool(workspace, db_dir=workspace / ".nexus-agent" / "runtime" / "rag"),
        TodoWriteTool(persist_path=workspace / ".nexus-agent" / "runtime" / "todos.json"),
        FormalCheckTool(workspace),
    ]
    if memory_manager is not None:
        from nexus_agent.tools.memory import MemoryTool
        memory = MemoryTool()
        memory.set_memory(memory_manager)
        tools.append(memory)

    if research:
        run_id = session_id or team_id or "interactive"
        from nexus_agent.research.configured_source_tool import ResearchConfiguredSourceTool
        from nexus_agent.storage.layout import StorageLayout
        from nexus_agent.research.tools import (
            ResearchRecordClaimTool,
            ResearchRecordSourceTool,
            ResearchVerifyClaimTool,
        )
        research_db = StorageLayout(workspace).workspace_runtime / "research.db"
        research_tools = [
            ResearchConfiguredSourceTool(
                workspace / ".nexus-agent" / "research-sources.yaml",
                research_db,
                run_id,
                agent_id or "interactive-agent",
            ),
            ResearchRecordClaimTool(research_db, run_id, agent_id or "interactive-agent"),
            ResearchVerifyClaimTool(research_db, run_id, agent_id or "interactive-agent"),
        ]
        if research_source_strategy != "user_only":
            research_tools.insert(
                1,
                ResearchRecordSourceTool(
                    research_db,
                    run_id,
                    agent_id or "interactive-agent",
                ),
            )
        tools.extend(research_tools)
        if research_source_strategy == "user_only":
            tools = [
                tool
                for tool in tools
                if getattr(tool, "name", "") not in {"web_search", "web_fetch", "webfetch", "browser"}
            ]

    if mcp_tools:
        tools.extend(mcp_tools)
    if include_advanced:
        boomerang = BoomerangTool(agent_loop)
        council = CouncilTool(provider)
        tools.extend([boomerang, council])
    return tools



class TeamRuntime:
    def __init__(
        self,
        provider: LLMProvider,
        tools: list[Any],
        workspace: Path | None = None,
        data_dir: Path | None = None,
        permission_callback: PermissionCallback | None = None,
        provider_selector: ProviderSelector | None = None,
        agent_registry: AgentRegistry | None = None,
        mcp_clients: list[Any] | None = None,
    ):
        self.provider = provider
        self.tools = list(tools)
        self.workspace = (workspace or Path.cwd()).resolve()
        self.data_dir = data_dir or StorageLayout(self.workspace).workspace_runtime
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.permission_callback = permission_callback
        self.provider_selector = provider_selector
        self.agent_registry = agent_registry or AgentRegistry(self.workspace)
        from nexus_agent.core.config import get_data_dir
        self.skill_registry = SkillRegistry(
            search_dirs=[
                str(Path(get_data_dir()) / "skills"),
                str(self.workspace / ".nexus-agent" / "skills"),
            ],
            workspace=self.workspace,
        )
        self.skill_registry.discover_skills()
        self.mcp_clients = list(mcp_clients or [])

    def close(self) -> None:
        """Release external runtime resources owned by this team runtime."""
        for client in list(self.mcp_clients):
            try:
                client.close()
            except (OSError, RuntimeError, ValueError):
                pass
        self.mcp_clients.clear()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


    def _make_store(self) -> TeamStore:
        return TeamStore(self.data_dir / "teams.db")

    @staticmethod
    def _tool_matches(name: str, categories: set[str]) -> bool:
        lowered = name.lower()
        if "read" in categories or "search" in categories:
            if lowered in {"read_file", "list_directory", "search_files", "repository_rag", "memory", "memory_scoped"}:
                return True
            if any(token in lowered for token in ("graph", "intel", "todo", "search")):
                return True
        if "write" in categories and lowered in {"write_file", "code_edit", "insert_lines", "batch_edit", "delete_file", "move_file"}:
            return True
        if "shell" in categories and lowered == "shell":
            return True
        if "web" in categories and lowered in {"web_search", "web_fetch", "webfetch", "browser"}:
            return True
        if "git" in categories and ("git" in lowered or lowered in {"ci_analyzer", "pr_generator", "smart_commit"}):
            return True
        if "parse" in categories and lowered == "parse_data":
            return True
        if "formal" in categories and lowered == "formal_check":
            return True
        if "code_intel" in categories and lowered in {"import_graph", "call_graph", "rename_symbol"}:
            return True
        if "lsp" in categories and lowered == "lsp_query":
            return True
        if "browser" in categories and lowered == "browser":
            return True
        if "delegate" in categories and lowered == "boomerang":
            return True
        if "council" in categories and lowered == "council":
            return True
        if "mcp" in categories and lowered.startswith("mcp."):
            return True
        return False

    def _tools_for(
        self,
        profile: AgentProfile,
        store: TeamStore,
        team_id: str,
        config: TeamConfig | None = None,
        worker_provider: LLMProvider | None = None,
        worker_agent_loop: Any | None = None,
    ) -> list[Any]:
        categories = set(profile.tool_categories)
        provider = worker_provider or self.provider

        # Build a fresh tool graph for every worker. Mutable tools such as
        # BrowserTool, RAG, LSP and nested delegation must never be shared
        # concurrently between independent AgentLoop instances.
        mcp_tools = [
            tool for tool in self.tools
            if getattr(tool, "is_mcp", False)
        ]
        fresh_catalog = build_workspace_tools(
            self.workspace,
            provider=provider,
            agent_loop=worker_agent_loop,
            mcp_tools=mcp_tools,
        )

        selected: list[Any] = []
        selected_names: set[str] = set()
        for tool in fresh_catalog + self.tools:
            name = str(getattr(tool, "name", ""))
            if name in selected_names:
                continue
            lowered = name.lower()
            allowed = self._tool_matches(name, categories)
            if "mcp" in categories and bool(getattr(tool, "is_mcp", False)):
                allowed = True
            if (
                lowered in {
                    "write_file",
                    "code_edit",
                    "insert_lines",
                    "batch_edit",
                    "delete_file",
                    "move_file",
                    "restore_file",
                    "rename_symbol",
                }
                and not profile.write_access
            ):
                allowed = False
            if allowed:
                selected.append(tool)
                selected_names.add(name)

        if profile.skill_ids:
            for skill_id in profile.skill_ids:
                skill = self.skill_registry.get_skill(skill_id)
                if skill is not None and getattr(skill, "name", "") not in selected_names:
                    selected.append(skill)
                    selected_names.add(getattr(skill, "name", ""))

        from nexus_agent.memory.scoped import ScopedMemory
        from nexus_agent.storage.layout import StorageLayout
        from nexus_agent.tools.scoped_memory import ScopedMemoryTool

        selected.append(
            ScopedMemoryTool(
                ScopedMemory(
                    StorageLayout(self.workspace),
                    agent_id=profile.role_id,
                    team_id=team_id,
                )
            )
        )
        selected.extend(
            [
                TeamSendMessageTool(store, team_id, profile.role_id),
                TeamReadMessagesTool(store, team_id, profile.role_id),
            ]
        )

        if "research" in categories:
            from nexus_agent.research.configured_source_tool import ResearchConfiguredSourceTool
            from nexus_agent.research.tools import (
                ResearchAdjudicateConflictTool,
                ResearchRecordClaimTool,
                ResearchRecordConflictTool,
                ResearchRecordSourceTool,
                ResearchVerifyClaimTool,
            )
            research_db = self.data_dir / "research.db"
            research_tools = [
                ResearchConfiguredSourceTool(
                    self.workspace / ".nexus-agent" / "research-sources.yaml",
                    research_db,
                    team_id,
                    profile.role_id,
                ),
                ResearchRecordClaimTool(research_db, team_id, profile.role_id),
                ResearchVerifyClaimTool(research_db, team_id, profile.role_id),
                ResearchRecordConflictTool(research_db, team_id, profile.role_id),
                ResearchAdjudicateConflictTool(research_db, team_id, profile.role_id),
            ]
            if config is None or config.research_source_strategy != "user_only":
                research_tools.insert(1, ResearchRecordSourceTool(research_db, team_id, profile.role_id))
            selected.extend(research_tools)
            if config is not None and config.research_source_strategy == "user_only":
                selected = [
                    tool
                    for tool in selected
                    if getattr(tool, "name", "") not in {"web_search", "webfetch", "browser"}
                ]

        return selected


    def _permission(
        self,
        tool_call: Any,
        config: TeamConfig,
        profile: AgentProfile | None = None,
        tool_catalog: list[Any] | None = None,
    ) -> bool:
        if config.auto_approve_tools:
            return True
        if self.permission_callback is not None:
            return bool(self.permission_callback(tool_call))

        name = str(getattr(tool_call, "name", "")).lower()
        arguments = getattr(tool_call, "arguments", {}) or {}
        if not isinstance(arguments, dict):
            arguments = {}
        catalog = tool_catalog if tool_catalog is not None else self.tools

        # Team coordination is a runtime protocol, not workspace mutation.
        # A specialist must be able to communicate and read its handoffs even
        # when it has no code/write permissions.
        if name in {"team_send_message", "team_read_messages"}:
            return True

        # Delegation is explicitly opted into through the delegate tool category.
        if name == "boomerang":
            return bool(profile and "delegate" in set(profile.tool_categories))

        # Stateful tools expose safe read-only actions alongside mutations.
        # Allow those read operations to read-only specialists while keeping
        # persistence/deletion behind the normal write boundary.
        if name == "memory_scoped" and str(arguments.get("action", "")).lower() in {"search", "stats"}:
            return True
        if name == "todowrite" and str(arguments.get("action", "")).lower() in {"list", "get"}:
            return True
        tool = next(
            (candidate for candidate in catalog if getattr(candidate, "name", "").lower() == name),
            None,
        )
        if tool is None and profile is not None and name in {item.lower() for item in profile.skill_ids}:
            tool = self.skill_registry.get_skill(name)

        level = str(getattr(tool, "permission_level", "ask")).lower() if tool else "ask"
        if level == "read-only":
            return True
        if level in {"dangerous", "ask"}:
            return False
        if level == "read-write":
            if name == "git":
                subcommand = str(arguments.get("subcommand", "")).strip().lower()
                safe_git_reads = {
                    "status",
                    "log",
                    "diff",
                    "show",
                    "describe",
                    "version",
                }
                if subcommand in safe_git_reads:
                    return True
                if subcommand == "remote":
                    raw_args = str(arguments.get("args", "")).strip()
                    if raw_args in {"", "-v", "--verbose", "get-url", "--get-url"}:
                        return True

            research_write = (
                profile is not None
                and "research" in set(profile.tool_categories)
                and name.startswith("research_")
            )
            return bool(profile and profile.write_access) or research_write

        return False

    def _system_extra(self, goal: str, profile: AgentProfile, team_id: str, config: TeamConfig) -> str:
        research_protocol = ""
        if "research" in profile.tool_categories:
            from .research import policy as research_policy
            depth = research_policy(config.research_depth)
            source_line = (
                "Only use the user-configured/seeded sources; autonomous discovery is disabled."
                if config.research_source_strategy == "user_only"
                else "You may discover new sources autonomously."
                if config.research_source_strategy == "autonomous"
                else "Use user-configured sources first and expand autonomously when useful."
            )
            role_text = f"{profile.role_id} {profile.name} {profile.profession}".lower()
            if any(term in role_text for term in ("researcher", "source", "bibliography", "metadata", "academic", "historian")):
                budget_line = f"Own the source-breadth budget: seek at least {depth['sources_per_round']} distinct source(s) in each turn and preserve provenance."
            elif any(term in role_text for term in ("verifier", "evidence", "citation", "claim-auditor")):
                budget_line = f"Own the verification budget: complete {depth['verification_passes']} verification pass(es) over high-value claims."
            elif any(term in role_text for term in ("skeptic", "contradiction", "conflict")):
                budget_line = f"Own the contradiction budget: perform {depth['contradiction_passes']} contradiction/counterevidence pass(es)."
            elif "formal" in role_text or "proof" in role_text or "model-check" in role_text:
                budget_line = f"Own the formal budget: attempt {depth['formal_passes']} formal-analysis/proof-check pass(es)."
            elif any(term in role_text for term in ("reviewer", "auditor")):
                budget_line = f"Own the review budget: perform {depth['review_passes']} independent review pass(es)."
            else:
                budget_line = "Integrate findings from peers and close evidence gaps within your professional specialization."
            research_protocol = (
                f"8. Research depth policy: {depth['label']}. "
                f"Team coordination is bounded; your role-specific depth budget is explicit. {budget_line} "
                f"Collection strategy: {config.research_collection}. {source_line} "
                f"Seed URLs: {', '.join(config.research_source_urls[:20]) or 'none'}."
                " Use research_configured_source when operating under user_only; otherwise "
                "use research_record_source to fetch and persist authoritative source text. "
                "Do not manually invent or transcribe source snapshots. Record factual claims "
                "with exact quotations using research_record_claim, and use research_verify_claim "
                "before treating quotation-backed evidence as deterministically verified."
            )
        return f"""
You are {profile.name}, a specialist worker in NexusAgent team {team_id}.
Profession: {profile.profession}
Mission: {profile.mission}

Team objective:
{goal}

Enabled reusable skills:
{", ".join(profile.skill_ids) if profile.skill_ids else "none"}

Your assigned instructions:
{profile.instructions}

Team protocol:
1. You are one peer worker, not the entire team.
2. Use team_send_message to publish important findings, questions, warnings, handoffs and review requests.
3. Use team_read_messages to receive messages from peers.
4. Do not claim that another worker's work is your own.
5. Record concrete evidence: file paths, commands, tests, source URLs, or artifact identifiers.
6. Stay within your profession and report blockers early.
7. Complete your own task cleanly even when other workers fail.
{research_protocol}
"""

    def _provider_for(self, profile: AgentProfile) -> LLMProvider:
        if self.provider_selector is None:
            return self.provider
        try:
            return self.provider_selector(profile)
        except (RuntimeError, ValueError, OSError, TypeError) as exc:
            raise RuntimeError(f"Unable to resolve provider for agent {profile.role_id}: {exc}") from exc

    def _worker(
        self,
        profile: AgentProfile,
        agent_storage_id: str,
        team_id: str,
        goal: str,
        config: TeamConfig,
        store: TeamStore,
        events: queue.Queue,
        control_state: Any,
    ) -> dict[str, Any]:
        started = time.time()
        store.update_agent(agent_storage_id, state=TeamAgentState.RUNNING.value, started_at=started)
        store.event(
            team_id,
            "agent_started",
            {"profession": profile.profession, "mission": profile.mission, "model_role": profile.model_role},
            profile.role_id,
        )
        events.put(
            AgentEvent(
                AgentEventType.STATE_CHANGE,
                {"team_id": team_id, "agent_id": profile.role_id, "state": TeamAgentState.RUNNING.value},
            )
        )
        store.message(
            team_id,
            "orchestrator",
            "TASK_ASSIGNMENT",
            {"agent": profile.name, "mission": profile.mission},
            recipient_id=profile.role_id,
        )

        from nexus_agent.memory.scoped import MemoryScope, ScopedMemory
        from nexus_agent.storage.layout import StorageLayout
        scoped_memory = ScopedMemory(
            StorageLayout(self.workspace),
            agent_id=profile.role_id,
            team_id=team_id,
        )
        prior_memory = scoped_memory.search(
            goal,
            scopes=[
                MemoryScope.WORKSPACE,
                MemoryScope.PROJECT,
                MemoryScope.USER,
                MemoryScope.TEAM,
                MemoryScope.AGENT,
            ],
            limit=8,
        )
        memory_context = ""
        if prior_memory:
            memory_context = "\n\nRelevant persistent context:\n" + "\n".join(
                f"- [{item.get('scope')}] {str(item.get('content', ''))[:1200]}"
                for item in prior_memory
            )

        cfg = AgentLoopConfig(
            mode=(
                AgentMode.RESEARCH
                if "research" in profile.tool_categories
                else AgentMode.BUILD
                if profile.write_access
                else AgentMode.REVIEW
            ),
            workspace=self.workspace,
            max_iterations=config.max_iterations_per_agent,
            system_prompt_extra=self._system_extra(goal, profile, team_id, config) + memory_context,
            effort_level=config.effort_level,
        )
        worker_provider = self._provider_for(profile)
        store.event(
            team_id,
            "agent_provider_resolved",
            {"provider": worker_provider.name, "model": worker_provider.model_name},
            profile.role_id,
        )
        worker_tools = self._tools_for(profile, store, team_id, config)
        agent = AgentLoop(
            provider=worker_provider,
            tools=worker_tools,
            config=cfg,
            permission_callback=lambda tc: self._permission(
                tc,
                config,
                profile,
                worker_tools,
            ),
        )
        for tool in worker_tools:
            if hasattr(tool, "set_agent_loop"):
                tool.set_agent_loop(agent)
            if hasattr(tool, "set_provider"):
                tool.set_provider(worker_provider)

        chunks: list[str] = []
        round_results: list[str] = []
        try:
            research_mode = "research" in profile.tool_categories
            if research_mode:
                from .research import policy as research_policy
                policy_data = research_policy(config.research_depth)
                coordination_cap = max(5, min(int(policy_data["coordination_turns"]), 10))
                # Post-deployment coordination is deliberately bounded to five-to-ten
                # turns. Deeper research spends more work inside each turn.
                if config.research_collection == "bounded":
                    max_rounds = min(coordination_cap, max(1, int(policy_data["query_rounds"])))
                elif config.research_collection == "until_saturation":
                    max_rounds = min(coordination_cap, max(1, int(policy_data["query_rounds"])))
                else:
                    max_rounds = coordination_cap
            else:
                max_rounds = 1

            started_monotonic = time.monotonic()
            idle_rounds = 0
            round_index = 0

            while max_rounds == 0 or round_index < max_rounds:
                persisted_control = store.pop_control(team_id)
                if persisted_control == "pause":
                    control_state.pause_requested.set()
                elif persisted_control == "resume":
                    control_state.pause_requested.clear()
                elif persisted_control == "stop":
                    control_state.stop_requested.set()

                if control_state.stop_requested.is_set():
                    store.update_agent(
                        agent_storage_id,
                        state=TeamAgentState.CANCELLED.value,
                        ended_at=time.time(),
                        error="Cancelled by user.",
                    )
                    store.event(team_id, "agent_cancelled", {"round": round_index + 1}, profile.role_id)
                    return {
                        "agent_id": profile.role_id,
                        "name": profile.name,
                        "profession": profile.profession,
                        "status": TeamAgentState.CANCELLED.value,
                        "result": "\n\n".join(round_results),
                        "reviewer": profile.reviewer,
                        "error": "Cancelled by user.",
                    }

                if control_state.pause_requested.is_set():
                    store.update_agent(agent_storage_id, state=TeamAgentState.WAITING_AGENT.value)
                    store.set_status(team_id, "paused")
                    while control_state.pause_requested.is_set() and not control_state.stop_requested.is_set():
                        persisted_control = store.pop_control(team_id)
                        if persisted_control == "resume":
                            control_state.pause_requested.clear()
                        elif persisted_control == "stop":
                            control_state.stop_requested.set()
                        time.sleep(0.5)
                    if control_state.stop_requested.is_set():
                        continue
                    store.update_agent(agent_storage_id, state=TeamAgentState.RUNNING.value)
                    store.set_status(team_id, "running")

                round_index += 1
                before_sources = 0
                research_store = None
                if research_mode:
                    from nexus_agent.research.store import ResearchStore
                    research_store = ResearchStore(self.data_dir / "research.db")
                    before_sources = len(research_store.sources(team_id))
                    store.event(
                        team_id,
                        "research_round_started",
                        {
                            "round": round_index,
                            "coordination_turn": round_index,
                            "coordination_turn_cap": max_rounds,
                            "depth": config.research_depth,
                            "depth_policy": policy_data,
                            "collection": config.research_collection,
                            "source_strategy": config.research_source_strategy,
                            "source_count_before": before_sources,
                        },
                        profile.role_id,
                    )

                round_chunks: list[str] = []
                round_had_error = False
                round_goal = (
                    f"{goal}\n\nYour specific assignment: {profile.mission}"
                    f"\n\nRole instructions:\n{profile.instructions}"
                )
                if research_mode:
                    round_goal += (
                        f"\n\nThis is evidence-gathering coordination turn {round_index} of {max_rounds}. "
                        f"At this depth target at least {policy_data['sources_per_round']} distinct source(s), "
                        f"{policy_data['verification_passes']} verification pass(es), "
                        f"{policy_data['contradiction_passes']} contradiction pass(es), "
                        f"{policy_data['formal_passes']} formal-analysis pass(es), and "
                        f"{policy_data['review_passes']} review pass(es). "
                        "Inspect existing ledger evidence first. Seek genuinely new or stronger "
                        "evidence, close unresolved gaps, challenge prior findings, and avoid "
                        "duplicate collection. Record exact source snapshots and quotations."
                    )

                agent = AgentLoop(
                    provider=worker_provider,
                    tools=worker_tools,
                    config=cfg,
                    permission_callback=lambda tc: self._permission(
                        tc,
                        config,
                        profile,
                        worker_tools,
                    ),
                )
                for tool in worker_tools:
                    if hasattr(tool, "set_agent_loop"):
                        tool.set_agent_loop(agent)
                    if hasattr(tool, "set_provider"):
                        tool.set_provider(worker_provider)

                for event in agent.run(round_goal):
                    store.event(
                        team_id,
                        "agent_event",
                        {
                            "event_type": event.type.value,
                            "data": event.data,
                            "timestamp": event.timestamp,
                            "round": round_index,
                        },
                        profile.role_id,
                    )
                    events.put(
                        AgentEvent(
                            event.type,
                            {
                                "team_id": team_id,
                                "agent_id": profile.role_id,
                                "data": event.data,
                                "round": round_index,
                            },
                            event.timestamp,
                        )
                    )
                    if event.type == AgentEventType.ERROR:
                        round_had_error = True
                    elif event.type == AgentEventType.CONTENT_CHUNK:
                        round_chunks.append(str(event.data or ""))
                    elif event.type == AgentEventType.CONTENT_COMPLETE:
                        round_chunks = [str(event.data or "")]

                if round_had_error:
                    raise RuntimeError(
                        f"Worker emitted an agent error event during round {round_index}."
                    )

                round_result = "".join(round_chunks).strip()
                if round_result:
                    round_results.append(f"[Round {round_index}]\n{round_result}")
                chunks = list(round_chunks)

                if research_store is not None:
                    after_sources = len(research_store.sources(team_id))
                    delta = max(0, after_sources - before_sources)
                    research_store.close()
                    research_store = None
                    if delta == 0:
                        idle_rounds += 1
                    else:
                        idle_rounds = 0
                    store.event(
                        team_id,
                        "research_round_completed",
                        {
                            "round": round_index,
                            "coordination_turn": round_index,
                            "coordination_turn_cap": max_rounds,
                            "depth": config.research_depth,
                            "depth_policy": policy_data,
                            "source_count_before": before_sources,
                            "source_count_after": after_sources,
                            "new_distinct_sources": delta,
                            "idle_rounds": idle_rounds,
                        },
                        profile.role_id,
                    )
                    if config.research_collection == "until_saturation" and idle_rounds >= config.research_idle_rounds:
                        store.event(
                            team_id,
                            "research_saturation_reached",
                            {"round": round_index, "idle_rounds": idle_rounds},
                            profile.role_id,
                        )
                        break
                    if (
                        config.research_collection == "continuous"
                        and time.monotonic() - started_monotonic >= config.research_max_minutes * 60
                    ):
                        store.event(
                            team_id,
                            "research_safety_deadline_reached",
                            {"round": round_index, "max_minutes": config.research_max_minutes},
                            profile.role_id,
                        )
                        break
                else:
                    break

            result = "\n\n".join(round_results).strip()
            store.update_agent(
                agent_storage_id,
                state=TeamAgentState.COMPLETED.value,
                ended_at=time.time(),
                result=result,
            )
            from nexus_agent.memory.scoped import MemoryScope
            if result:
                scoped_memory.store(
                    result[-5000:],
                    scope=MemoryScope.TEAM,
                    category=f"team_result:{profile.role_id}",
                    metadata={"team_id": team_id, "agent_id": profile.role_id},
                )
                scoped_memory.store(
                    result[-3000:],
                    scope=MemoryScope.AGENT,
                    category="completed_work",
                    metadata={"team_id": team_id, "agent_id": profile.role_id},
                )
            store.message(
                team_id,
                profile.role_id,
                "COMPLETION",
                {"summary": result[-4000:]},
            )
            events.put(
                AgentEvent(
                    AgentEventType.DONE,
                    {
                        "team_id": team_id,
                        "agent_id": profile.role_id,
                        "status": TeamAgentState.COMPLETED.value,
                        "result": result,
                    },
                )
            )
            return {
                "agent_id": profile.role_id,
                "name": profile.name,
                "profession": profile.profession,
                "status": TeamAgentState.COMPLETED.value,
                "result": result,
                "reviewer": profile.reviewer,
            }
        except (RuntimeError, ValueError, OSError, TypeError) as exc:
            store.update_agent(
                agent_storage_id,
                state=TeamAgentState.FAILED.value,
                ended_at=time.time(),
                error=str(exc),
            )
            store.message(team_id, profile.role_id, "FAILURE", {"error": str(exc)})
            events.put(
                AgentEvent(
                    AgentEventType.ERROR,
                    {"team_id": team_id, "agent_id": profile.role_id, "error": str(exc)},
                )
            )
            return {
                "agent_id": profile.role_id,
                "name": profile.name,
                "profession": profile.profession,
                "status": TeamAgentState.FAILED.value,
                "result": "",
                "reviewer": profile.reviewer,
                "error": str(exc),
            }
        finally:
            if research_store is not None:
                research_store.close()
            scoped_memory.close()

    def _write_artifacts(
        self,
        team_id: str,
        goal: str,
        summary: str,
        synthesis: str,
        results: list[dict[str, Any]],
        config: TeamConfig,
        quality: dict[str, Any] | None = None,
    ) -> list[str]:
        if config.output_mode not in {"file", "both"}:
            return []
        artifact_dir = self.data_dir / "artifacts" / team_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        content = synthesis or summary
        if config.output_format == "text":
            path = artifact_dir / "result.txt"
            path.write_text(content, encoding="utf-8")
        elif config.output_format == "json":
            import json
            path = artifact_dir / "result.json"
            path.write_text(
                json.dumps(
                    {
                        "team_id": team_id,
                        "goal": goal,
                        "summary": summary,
                        "synthesis": synthesis,
                        "agents": results,
                        "quality": quality or {},
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        else:
            path = artifact_dir / "result.md"
            lines = [
                "# NexusAgent Team Result",
                "",
                "Team: " + team_id,
                "",
                "## Goal",
                "",
                goal,
                "",
                "## Summary",
                "",
                summary,
                "",
                "## Synthesis",
                "",
                content,
                "",
                "## Evidence Quality Gate",
                "",
                json.dumps(quality or {}, ensure_ascii=False, indent=2),
                "",
                "## Workers",
                "",
            ]
            for item in results:
                lines.extend(
                    [
                        "### " + str(item.get("name", item.get("agent_id", "worker"))),
                        "",
                        "Profession: " + str(item.get("profession", "")),
                        "",
                        str(item.get("result", "") or item.get("error", "")),
                        "",
                    ]
                )
            path.write_text("\n".join(lines), encoding="utf-8")
        return [str(path.resolve())]

    def _synthesize(
        self,
        team_id: str,
        goal: str,
        results: list[dict[str, Any]],
        store: TeamStore,
        research_claims: list[dict[str, Any]] | None = None,
    ) -> str:
        compact = [
            {
                "agent_id": item.get("agent_id"),
                "name": item.get("name"),
                "profession": item.get("profession"),
                "status": item.get("status"),
                "result": str(item.get("result", ""))[-12000:],
            }
            for item in results
            if item.get("status") == TeamAgentState.COMPLETED.value
        ]
        if not compact:
            return ""
        if research_claims is not None and not research_claims:
            store.event(
                team_id,
                "research_report_suppressed",
                {"reason": "No verified claims were available for factual synthesis."},
            )
            return (
                "Evidence gate did not produce any verified claims. "
                "No factual research report was emitted."
            )

        system = (
            "You are the integration lead for a NexusAgent team. "
            "Synthesize only the supplied worker results. Do not invent facts. "
            "Call out disagreement and missing evidence explicitly."
        )
        user = f"Goal:\n{goal}\n\nWorker results:\n{json_dump(compact)}"
        if research_claims is not None:
            system = (
                "You are the evidence-bound integration lead for a NexusAgent research team. "
                "Use the verified claim ledger as the only authority for factual statements. "
                "Every factual statement must include one or more [claim:N] markers corresponding "
                "to supplied verified claims. Include source URLs where useful. Do not use "
                "unverified worker prose as factual evidence. Explicitly state unresolved gaps."
            )
            user += (
                f"\n\nVerified claim ledger:\n{json_dump(research_claims)}"
                "\n\nProduce the integrated research result. Preserve [claim:N] markers."
            )
        else:
            user += "\n\nProduce a concise integrated result."

        response = self.provider.chat_completion(
            [
                Message(role=Role.SYSTEM, content=system),
                Message(role=Role.USER, content=user),
            ],
            temperature=0.1,
            max_tokens=8000,
        )
        synthesis = response.content or ""
        store.event(
            team_id,
            "team_synthesis",
            {
                "content": synthesis,
                "evidence_bound": research_claims is not None,
                "verified_claim_count": len(research_claims or []),
            },
        )
        return synthesis

    def run(self, goal: str, config: TeamConfig | None = None) -> Iterator[AgentEvent]:
        cfg = (config or TeamConfig()).normalize()
        cfg.workspace = str(self.workspace)
        effective_mode = infer_mode(goal, cfg.mode)
        cfg.mode = effective_mode
        cfg.normalize()
        saved_specs = []
        if cfg.use_saved_agents:
            relevant = self.agent_registry.match_relevant(goal, limit=16)
            pinned_specs = []
            for agent_id in cfg.agent_ids:
                spec = self.agent_registry.get(agent_id)
                if spec is not None:
                    pinned_specs.append(spec)
            seen_saved: set[str] = set()
            for spec in [*pinned_specs, *relevant]:
                if spec.id not in seen_saved:
                    saved_specs.append(spec)
                    seen_saved.add(spec.id)
        saved_profiles = [spec.to_team_profile() for spec in saved_specs]
        if cfg.research_source_urls:
            from nexus_agent.research.sources import ResearchSourceRegistry
            ResearchSourceRegistry(
                self.workspace / ".nexus-agent" / "research-sources.yaml"
            ).seed_urls(cfg.research_source_urls)
        mode, profiles = generate_team(self.provider, goal, cfg, saved_agents=saved_profiles)
        pinned: list[AgentProfile] = []
        pinned_ids: set[str] = set()
        for agent_id in cfg.agent_ids:
            normalized_id = agent_id.strip().lower()
            profile = next(
                (item for item in saved_profiles if item.role_id == normalized_id),
                None,
            )
            if profile is None:
                built_in = self.agent_registry.get(normalized_id)
                profile = built_in.to_team_profile() if built_in is not None else None
            if profile is not None and profile.role_id not in pinned_ids:
                pinned.append(profile)
                pinned_ids.add(profile.role_id)
        if pinned:
            remainder = [item for item in profiles if item.role_id not in pinned_ids]
            profiles = (pinned + remainder)[: cfg.max_agents]

        team_id = uuid.uuid4().hex[:12]
        store = self._make_store()
        control_state = register_team_control(team_id)
        events: queue.Queue[AgentEvent] = queue.Queue()
        store.create_team(
            team_id,
            goal,
            mode.value,
            str(self.workspace),
            cfg.__dict__,
        )
        if mode == TeamMode.RESEARCH:
            from .research import policy as research_policy
            store.event(
                team_id,
                "research_policy",
                {
                    "depth": cfg.research_depth,
                    "policy": research_policy(cfg.research_depth),
                    "collection": cfg.research_collection,
                    "source_strategy": cfg.research_source_strategy,
                    "seed_urls": list(cfg.research_source_urls),
                    "max_minutes": cfg.research_max_minutes,
                    "idle_rounds": cfg.research_idle_rounds,
                },
            )

        agent_storage_ids: dict[str, str] = {}
        for profile in profiles:
            agent_storage_ids[profile.role_id] = store.add_agent(team_id, profile.to_dict())
            store.event(team_id, "agent_planned", {"profile": profile.to_dict()}, profile.role_id)

        if mode == TeamMode.RESEARCH:
            from .research import policy as research_policy
            deployment_policy = research_policy(cfg.research_depth)
            store.event(
                team_id,
                "team_deployed",
                {
                    "agent_count": len(profiles),
                    "planning_phase": "complete",
                    "post_deployment_coordination_turn_cap": deployment_policy["coordination_turns"],
                    "research_depth": cfg.research_depth,
                },
            )
            store.event(
                team_id,
                "workflow_phase",
                {"from": "planning", "to": "execution", "reason": "professional team deployed"},
            )
        yield AgentEvent(
            AgentEventType.STATE_CHANGE,
            {
                "team_id": team_id,
                "state": "running",
                "mode": mode.value,
                "agent_count": len(profiles),
            },
        )

        research_deadline = None
        if mode == TeamMode.RESEARCH and cfg.research_max_minutes > 0:
            research_deadline = time.time() + (cfg.research_max_minutes * 60)

        # Dependency-aware scheduler: independent agents run concurrently;
        # dependent agents are released only after their prerequisites complete.
        profile_by_id = {profile.role_id: profile for profile in profiles}
        pending = set(profile_by_id)
        completed_ids: set[str] = set()
        failed_ids: set[str] = set()
        active: dict[Any, AgentProfile] = {}
        coordination_turn = 0
        coordination_turn_cap = None
        if mode == TeamMode.RESEARCH:
            from .research import policy as research_policy
            coordination_turn_cap = int(research_policy(cfg.research_depth)["coordination_turns"])

        with ThreadPoolExecutor(
            max_workers=cfg.parallelism,
            thread_name_prefix=f"nexus-team-{team_id}",
        ) as pool:
            while pending or active:
                if research_deadline is not None and time.time() >= research_deadline:
                    store.event(team_id, "research_deadline_reached", {"max_minutes": cfg.research_max_minutes})
                    control_state.stop_requested.set()
                persisted_control = store.pop_control(team_id)
                if persisted_control == "pause":
                    control_state.pause_requested.set()
                elif persisted_control == "resume":
                    control_state.pause_requested.clear()
                elif persisted_control == "stop":
                    control_state.stop_requested.set()

                if control_state.stop_requested.is_set():
                    for role_id in sorted(pending):
                        store.update_agent(
                            agent_storage_ids[role_id],
                            state=TeamAgentState.CANCELLED.value,
                            ended_at=time.time(),
                            error="Cancelled by user.",
                        )
                        store.event(
                            team_id,
                            "agent_cancelled_before_start",
                            {"reason": "user_stop"},
                            role_id,
                        )
                    pending.clear()
                    break

                if control_state.pause_requested.is_set() and not active:
                    store.set_status(team_id, "paused")
                    yield AgentEvent(AgentEventType.STATE_CHANGE, {"team_id": team_id, "state": "paused"})
                    while control_state.pause_requested.is_set() and not control_state.stop_requested.is_set():
                        time.sleep(0.5)
                    if control_state.stop_requested.is_set():
                        continue
                    store.set_status(team_id, "running")
                    yield AgentEvent(AgentEventType.STATE_CHANGE, {"team_id": team_id, "state": "running"})

                # Unknown dependencies cannot ever unblock. Mark those workers
                # as failed/review-required instead of deadlocking the team.
                for role_id in sorted(pending):
                    profile = profile_by_id[role_id]
                    unknown = [
                        dep for dep in profile.dependencies
                        if dep not in profile_by_id
                    ]
                    if unknown:
                        store.update_agent(
                            agent_storage_ids[role_id],
                            state=TeamAgentState.FAILED.value,
                            ended_at=time.time(),
                            error=f"Unknown dependency: {', '.join(unknown)}",
                        )
                        failed_ids.add(role_id)
                        pending.remove(role_id)
                        store.event(
                            team_id,
                            "agent_dependency_error",
                            {"unknown_dependencies": unknown},
                            role_id,
                        )

                # Active workers constitute one coordination wave. Do not replenish
                # the wave until every member finishes; this makes the 5-10
                # post-deployment coordination-turn guarantee observable and testable.
                ready = [] if active else [
                    profile_by_id[role_id]
                    for role_id in sorted(pending)
                    if all(
                        dependency in completed_ids
                        for dependency in profile_by_id[role_id].dependencies
                    )
                ]

                if ready and coordination_turn_cap is not None and coordination_turn >= coordination_turn_cap:
                    store.event(
                        team_id,
                        "coordination_turn_cap_reached",
                        {
                            "turns_used": coordination_turn,
                            "turn_cap": coordination_turn_cap,
                            "remaining_agents": sorted(pending),
                        },
                    )
                    for role_id in sorted(pending):
                        store.update_agent(
                            agent_storage_ids[role_id],
                            state=TeamAgentState.FAILED.value,
                            ended_at=time.time(),
                            error="Research coordination-turn cap reached before deployment.",
                        )
                        store.event(
                            team_id,
                            "agent_not_deployed",
                            {"reason": "coordination_turn_cap_reached"},
                            role_id,
                        )
                    failed_ids.update(pending)
                    pending.clear()
                    ready = []

                if ready:
                    coordination_turn += 1
                    store.event(
                        team_id,
                        "coordination_turn_started",
                        {
                            "turn": coordination_turn,
                            "turn_cap": coordination_turn_cap,
                            "ready_agents": [profile.role_id for profile in ready],
                        },
                    )

                capacity = max(0, cfg.parallelism - len(active))
                for profile in ready[:capacity]:
                    if profile.role_id not in pending:
                        continue
                    pending.remove(profile.role_id)
                    future = pool.submit(
                        self._worker,
                        profile,
                        agent_storage_ids[profile.role_id],
                        team_id,
                        goal,
                        cfg,
                        store,
                        events,
                        control_state,
                    )
                    active[future] = profile

                if not active:
                    # Remaining pending work is blocked by a failed prerequisite
                    # or a dependency cycle. Surface this explicitly.
                    if pending:
                        for role_id in sorted(pending):
                            store.update_agent(
                                agent_storage_ids[role_id],
                                state=TeamAgentState.FAILED.value,
                                ended_at=time.time(),
                                error="Dependency cycle or failed prerequisite blocked this agent.",
                            )
                            store.event(
                                team_id,
                                "agent_dependency_blocked",
                                {"dependencies": profile_by_id[role_id].dependencies},
                                role_id,
                            )
                        failed_ids.update(pending)
                        pending.clear()
                    break

                done_future = next(as_completed(active))
                profile = active.pop(done_future)
                try:
                    result = done_future.result()
                except (RuntimeError, ValueError, OSError, TypeError) as exc:
                    result = {
                        "agent_id": profile.role_id,
                        "name": profile.name,
                        "profession": profile.profession,
                        "status": TeamAgentState.FAILED.value,
                        "result": "",
                        "reviewer": profile.reviewer,
                        "error": str(exc),
                    }
                    failed_ids.add(profile.role_id)
                else:
                    if result.get("status") == TeamAgentState.COMPLETED.value:
                        completed_ids.add(profile.role_id)
                    else:
                        failed_ids.add(profile.role_id)

                while True:
                    try:
                        yield events.get_nowait()
                    except queue.Empty:
                        break
                yield AgentEvent(AgentEventType.CONTENT, result)

            # Drain any late telemetry queued by completed workers.

        while True:
            try:
                yield events.get_nowait()
            except queue.Empty:
                break

        stored = store.agents(team_id)
        results = [
            {
                "agent_id": row["agent_id"],
                "name": row["name"],
                "profession": row["profession"],
                "status": row["state"],
                "result": row.get("result") or "",
                "error": row.get("error"),
                "reviewer": bool(json_load(row.get("role_json")).get("reviewer", False)),
            }
            for row in stored
        ]

        failures = [
            str(item.get("error") or "agent failed")
            for item in results
            if item.get("status") != TeamAgentState.COMPLETED.value
        ]
        reviewers = [
            item
            for item in results
            if item.get("reviewer") and item.get("status") == TeamAgentState.COMPLETED.value
        ]

        research_quality: dict[str, Any] | None = None
        if mode == TeamMode.RESEARCH:
            from .research import policy as research_policy
            from nexus_agent.research.store import ResearchStore

            research_store = ResearchStore(self.data_dir / "research.db")
            try:
                research_quality = research_store.coverage(
                    team_id,
                    research_policy(cfg.research_depth)["verification_passes"],
                )
            finally:
                research_store.close()
            store.event(team_id, "research_quality_gate", research_quality)

        research_claims: list[dict[str, Any]] | None = None
        if mode == TeamMode.RESEARCH:
            from nexus_agent.research.store import ResearchStore
            evidence_store = ResearchStore(self.data_dir / "research.db")
            try:
                research_claims = evidence_store.verified_claims(team_id)
            finally:
                evidence_store.close()

        store.event(
            team_id,
            "final_review_started",
            {
                "workflow": "post-deployment-final-review",
                "workers_completed": len(
                    [item for item in results if item.get("status") == TeamAgentState.COMPLETED.value]
                ),
                "reviewers_completed": len(reviewers),
                "verified_claim_count": len(research_claims or []),
            },
        )

        synthesis = ""
        summary = (
            f"{len([r for r in results if r['status'] == TeamAgentState.COMPLETED.value])}/"
            f"{len(results)} team workers completed"
        )
        if cfg.require_reviewer:
            summary += f"; reviewer={'present' if reviewers else 'missing'}"

        preliminary_quality = evaluate_team(
            results=results,
            config=cfg,
            artifacts=[],
            research_summary=research_quality,
        )
        if not preliminary_quality["passed"]:
            store.event(team_id, "team_quality_precheck_failed", preliminary_quality)

        if cfg.auto_synthesize:
            try:
                if mode == TeamMode.RESEARCH and research_quality and not research_quality.get("passed"):
                    store.event(
                        team_id,
                        "research_report_suppressed",
                        {
                            "reason": "Evidence quality gate failed; factual synthesis withheld.",
                            "quality": research_quality,
                        },
                    )
                    synthesis = (
                        "Evidence gate did not pass. No factual research report was emitted. "
                        "Resolve the outstanding source, claim and verification requirements."
                    )
                else:
                    synthesis = self._synthesize(
                        team_id,
                        goal,
                        results,
                        store,
                        research_claims=research_claims,
                    )
            except (RuntimeError, ValueError, OSError, TypeError) as exc:
                store.event(team_id, "team_synthesis_failed", {"error": str(exc)})
                failures.append(f"Team synthesis failed: {exc}")

        artifact_paths = self._write_artifacts(
            team_id,
            goal,
            summary,
            synthesis,
            results,
            cfg,
            preliminary_quality,
        )
        final_quality = evaluate_team(
            results=results,
            config=cfg,
            artifacts=artifact_paths,
            research_summary=research_quality,
            research_synthesis=synthesis if mode == TeamMode.RESEARCH else "",
        )
        success = bool(final_quality["passed"]) and not failures
        if failures:
            final_quality["passed"] = False
            final_quality["failure_reasons"] = list(failures)

        if artifact_paths:
            store.event(team_id, "artifacts_written", {"paths": artifact_paths})
        store.event(team_id, "team_quality_gate", final_quality)
        terminal_status = "cancelled" if control_state.stop_requested.is_set() else ("completed" if success else "needs_review")
        store.message(
            team_id,
            "orchestrator",
            "TEAM_COMPLETE",
            {"success": success, "status": terminal_status, "summary": summary},
        )
        store.finish_team(team_id, terminal_status, final_quality)

        result = TeamRunResult(
            team_id,
            goal,
            success,
            summary,
            results,
            synthesis,
            failures,
            artifact_paths,
            final_quality,
        )
        yield AgentEvent(AgentEventType.CONTENT_COMPLETE, synthesis or summary)
        yield AgentEvent(AgentEventType.DONE, result.__dict__)
        unregister_team_control(team_id)
        for client in self.mcp_clients:
            try:
                client.close()
            except (OSError, RuntimeError):
                pass
        store.close()

    def run_collect(self, goal: str, config: TeamConfig | None = None) -> TeamRunResult:
        final: TeamRunResult | None = None
        for event in self.run(goal, config):
            if event.type == AgentEventType.DONE and isinstance(event.data, dict):
                final = TeamRunResult(
                    team_id=str(event.data.get("team_id", "")),
                    goal=goal,
                    success=bool(event.data.get("success", False)),
                    summary=str(event.data.get("summary", "")),
                    agents=list(event.data.get("agents", [])),
                    synthesis=str(event.data.get("synthesis", "")),
                    failures=list(event.data.get("failures", [])),
                    artifact_paths=list(event.data.get("artifact_paths", [])),
                    quality=dict(event.data.get("quality", {})),
                )
        if final is None:
            raise RuntimeError("Team runtime ended without a final result.")
        return final


def json_dump(value: Any) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)


def json_load(value: Any) -> dict[str, Any]:
    import json
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}
