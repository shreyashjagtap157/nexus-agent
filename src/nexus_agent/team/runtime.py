"""Concurrent multi-agent team runtime."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterator

from nexus_agent.core.agent import AgentEvent, AgentEventType, AgentLoop, AgentLoopConfig, AgentMode
from nexus_agent.llm.base import LLMProvider, Message, Role

from .models import AgentProfile, TeamAgentState, TeamConfig, TeamMode, TeamRunResult
from .control import control as control_team_request, register as register_team_control, unregister as unregister_team_control
from .planner import generate_team
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
) -> list[Any]:
    from nexus_agent.tools.browser import BrowserTool
    from nexus_agent.tools.boomerang import BoomerangTool
    from nexus_agent.tools.batch_edit import BatchEditTool
    from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
    from nexus_agent.tools.code_intel import CallGraphTool, ImportGraphTool, RenameTool
    from nexus_agent.tools.council import CouncilTool
    from nexus_agent.tools.file_ops import (
        DeleteFileTool,
        ListDirectoryTool,
        MoveFileTool,
        ParseDataTool,
        ReadFileTool,
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
        ParseDataTool(workspace),
        SearchFilesTool(workspace),
        ListDirectoryTool(workspace),
        ShellTool(workspace),
        CodeEditTool(workspace),
        InsertLinesTool(workspace),
        BatchEditTool(workspace),
        GitTool(workspace),
        SmartCommitTool(workspace),
        PRGeneratorTool(workspace),
        CIAnalyzerTool(workspace),
        WebSearchTool(),
        WebFetchTool(),
        BrowserTool(workspace),
        ImportGraphTool(workspace),
        CallGraphTool(workspace),
        RenameTool(workspace),
        LSPClientTool(workspace),
        RepositoryRAGTool(workspace, db_dir=workspace / ".nexus-agent" / "runtime" / "rag"),
        TodoWriteTool(persist_path=workspace / ".nexus-agent" / "runtime" / "todos.json"),
    ]
    if memory_manager is not None:
        from nexus_agent.tools.memory import MemoryTool
        memory = MemoryTool()
        memory.set_memory(memory_manager)
        tools.append(memory)
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
    ):
        self.provider = provider
        self.tools = list(tools)
        self.workspace = (workspace or Path.cwd()).resolve()
        self.data_dir = data_dir or (self.workspace / ".nexus")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.permission_callback = permission_callback
        self.provider_selector = provider_selector

    def _make_store(self) -> TeamStore:
        return TeamStore(self.data_dir / "teams.db")

    @staticmethod
    def _tool_matches(name: str, categories: set[str]) -> bool:
        lowered = name.lower()
        if "read" in categories:
            if lowered in {"read_file", "list_directory", "search_files", "repository_rag", "memory"}:
                return True
            if any(token in lowered for token in ("graph", "intel", "todo", "search")):
                return True
        if "write" in categories and lowered in {"write_file", "code_edit", "insert_lines", "batch_edit"}:
            return True
        if "shell" in categories and lowered == "shell":
            return True
        if "web" in categories and lowered in {"web_search", "web_fetch", "webfetch", "browser"}:
            return True
        if "git" in categories and ("git" in lowered or lowered in {"ci_analyzer", "pr_generator"}):
            return True
        return False

    def _tools_for(self, profile: AgentProfile, store: TeamStore, team_id: str) -> list[Any]:
        categories = set(profile.tool_categories)
        selected = [
            tool for tool in self.tools
            if self._tool_matches(getattr(tool, "name", ""), categories)
            and (getattr(tool, "name", "").lower() not in {"write_file", "code_edit", "insert_lines", "batch_edit"} or profile.write_access)
        ]
        selected.extend(
            [
                TeamSendMessageTool(store, team_id, profile.role_id),
                TeamReadMessagesTool(store, team_id, profile.role_id),
            ]
        )
        if "research" in categories:
            from nexus_agent.research.tools import (
                ResearchRecordClaimTool,
                ResearchRecordSourceTool,
                ResearchVerifyClaimTool,
            )
            research_db = self.data_dir / "research.db"
            selected.extend(
                [
                    ResearchRecordSourceTool(research_db, team_id, profile.role_id),
                    ResearchRecordClaimTool(research_db, team_id, profile.role_id),
                    ResearchVerifyClaimTool(research_db, team_id, profile.role_id),
                ]
            )
        return selected

    def _permission(self, tool_call: Any, config: TeamConfig) -> bool:
        if config.auto_approve_tools:
            return True
        if self.permission_callback is not None:
            return bool(self.permission_callback(tool_call))
        # Safe team default: allow read/search/web/git introspection; deny
        # operations that the normal PermissionManager would require approval for.
        name = str(getattr(tool_call, "name", "")).lower()
        return not any(token in name for token in ("write", "edit", "insert", "shell", "commit", "push", "delete"))

    def _system_extra(self, goal: str, profile: AgentProfile, team_id: str) -> str:
        research_protocol = ""
        if "research" in profile.tool_categories:
            research_protocol = (
                "8. For research findings, preserve exact source text with research_record_source, "
                "record factual claims with exact quotations using research_record_claim, and use "
                "research_verify_claim before treating quotation-backed evidence as deterministically verified."
            )
        return f"""
You are {profile.name}, a specialist worker in NexusAgent team {team_id}.
Profession: {profile.profession}
Mission: {profile.mission}

Team objective:
{goal}

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

        cfg = AgentLoopConfig(
            mode=AgentMode.BUILD if profile.write_access else AgentMode.REVIEW,
            workspace=self.workspace,
            max_iterations=config.max_iterations_per_agent,
            system_prompt_extra=self._system_extra(goal, profile, team_id),
            effort_level=config.effort_level,
        )
        worker_provider = self._provider_for(profile)
        store.event(
            team_id,
            "agent_provider_resolved",
            {"provider": worker_provider.name, "model": worker_provider.model_name},
            profile.role_id,
        )
        agent = AgentLoop(
            provider=worker_provider,
            tools=self._tools_for(profile, store, team_id),
            config=cfg,
            permission_callback=lambda tc: self._permission(tc, config),
        )

        chunks: list[str] = []
        had_agent_error = False
        try:
            worker_goal = f"{goal}\n\nYour specific assignment: {profile.mission}\n\nRole instructions:\n{profile.instructions}"
            for event in agent.run(worker_goal):
                store.event(
                    team_id,
                    "agent_event",
                    {
                        "event_type": event.type.value,
                        "data": event.data,
                        "timestamp": event.timestamp,
                    },
                    profile.role_id,
                )
                events.put(
                    AgentEvent(
                        event.type,
                        {"team_id": team_id, "agent_id": profile.role_id, "data": event.data},
                        event.timestamp,
                    )
                )
                if event.type == AgentEventType.ERROR:
                    had_agent_error = True
                elif event.type == AgentEventType.CONTENT_CHUNK:
                    chunks.append(str(event.data or ""))
                elif event.type == AgentEventType.CONTENT_COMPLETE:
                    chunks = [str(event.data or "")]

            result = "".join(chunks).strip()
            if had_agent_error:
                raise RuntimeError("Worker emitted an agent error event; see team event log for details.")
            store.update_agent(
                agent_storage_id,
                state=TeamAgentState.COMPLETED.value,
                ended_at=time.time(),
                result=result,
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

    def _write_artifacts(
        self,
        team_id: str,
        goal: str,
        summary: str,
        synthesis: str,
        results: list[dict[str, Any]],
        config: TeamConfig,
    ) -> list[str]:
        if config.output_mode not in {"file", "both"}:
            return []
        artifact_dir = self.data_dir / "teams" / team_id
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

    def _synthesize(self, team_id: str, goal: str, results: list[dict[str, Any]], store: TeamStore) -> str:
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
        response = self.provider.chat_completion(
            [
                Message(
                    role=Role.SYSTEM,
                    content=(
                        "You are the integration lead for a NexusAgent team. "
                        "Synthesize only the supplied worker results. Do not invent facts. "
                        "Call out disagreement and missing evidence explicitly."
                    ),
                ),
                Message(
                    role=Role.USER,
                    content=(
                        f"Goal:\\n{goal}\\n\\nWorker results:\\n"
                        f"{json_dump(compact)}\\n\\nProduce a concise integrated result."
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=8000,
        )
        synthesis = response.content or ""
        store.event(team_id, "team_synthesis", {"content": synthesis})
        return synthesis

    def run(self, goal: str, config: TeamConfig | None = None) -> Iterator[AgentEvent]:
        cfg = (config or TeamConfig()).normalize()
        cfg.workspace = str(self.workspace)
        mode, profiles = generate_team(self.provider, goal, cfg)

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

        agent_storage_ids: dict[str, str] = {}
        for profile in profiles:
            agent_storage_ids[profile.role_id] = store.add_agent(team_id, profile.to_dict())
            store.event(team_id, "agent_planned", {"profile": profile.to_dict()}, profile.role_id)

        yield AgentEvent(
            AgentEventType.STATE_CHANGE,
            {
                "team_id": team_id,
                "state": "planned",
                "mode": mode.value,
                "agent_count": len(profiles),
            },
        )

        # Dependency-aware scheduler: independent agents run concurrently;
        # dependent agents are released only after their prerequisites complete.
        profile_by_id = {profile.role_id: profile for profile in profiles}
        pending = set(profile_by_id)
        completed_ids: set[str] = set()
        failed_ids: set[str] = set()
        active: dict[Any, AgentProfile] = {}

        with ThreadPoolExecutor(
            max_workers=cfg.parallelism,
            thread_name_prefix=f"nexus-team-{team_id}",
        ) as pool:
            while pending or active:
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

                ready = [
                    profile_by_id[role_id]
                    for role_id in sorted(pending)
                    if all(
                        dependency in completed_ids
                        for dependency in profile_by_id[role_id].dependencies
                    )
                    and all(
                        dependency in profile_by_id
                        for dependency in profile_by_id[role_id].dependencies
                    )
                ]

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
        success = not failures and (not cfg.require_reviewer or bool(reviewers))

        synthesis = ""
        if cfg.auto_synthesize:
            try:
                synthesis = self._synthesize(team_id, goal, results, store)
            except (RuntimeError, ValueError, OSError, TypeError) as exc:
                store.event(team_id, "team_synthesis_failed", {"error": str(exc)})
                if not failures:
                    failures.append(f"Team synthesis failed: {exc}")
                    success = False

        summary = (
            f"{len([r for r in results if r['status'] == TeamAgentState.COMPLETED.value])}/"
            f"{len(results)} team workers completed"
        )
        if cfg.require_reviewer:
            summary += f"; reviewer={'present' if reviewers else 'missing'}"
        store.message(team_id, "orchestrator", "TEAM_COMPLETE", {"success": success, "summary": summary})
        terminal_status = "cancelled" if control_state.stop_requested.is_set() else ("completed" if success else "needs_review")
        store.finish_team(team_id, terminal_status)

        artifact_paths = self._write_artifacts(
            team_id,
            goal,
            summary,
            synthesis,
            results,
            cfg,
        )
        if artifact_paths:
            store.event(team_id, "artifacts_written", {"paths": artifact_paths})
        result = TeamRunResult(
            team_id,
            goal,
            success,
            summary,
            results,
            synthesis,
            failures,
            artifact_paths,
        )
        yield AgentEvent(AgentEventType.CONTENT_COMPLETE, synthesis or summary)
        yield AgentEvent(AgentEventType.DONE, result.__dict__)
        unregister_team_control(team_id)
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
