from pathlib import Path

from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ProviderCapabilities
from nexus_agent.team import AgentProfile, TeamConfig, TeamMode, TeamRuntime


class FakeProvider(LLMProvider):
    def __init__(self, name="fake"):
        self._name = name
        self.calls = []

    @property
    def name(self): return self._name

    @property
    def model_name(self): return self._name + "-model"

    def get_capabilities(self):
        return ProviderCapabilities(
            supports_tool_calling=False,
            supports_streaming=True,
            supports_system_message=True,
            max_context_length=32000,
            max_output_tokens=4096,
        )

    def chat_completion(self, messages, tools=None, temperature=0.1, max_tokens=4096, **kwargs):
        self.calls.append(messages)
        system = messages[0].content if messages else ""
        if "team architect" in system.lower():
            return LLMResponse(
                content='{"agents":[{"name":"One","profession":"Engineer","mission":"First","instructions":"Do first","tool_categories":["read"],"write_access":false,"reviewer":false,"model_role":"default"},{"name":"Two","profession":"Engineer","mission":"Second","instructions":"Do second","tool_categories":["read"],"write_access":false,"reviewer":true,"dependencies":["one"],"model_role":"default"}]}',
                model=self.model_name,
            )
        if "integration lead" in system.lower():
            return LLMResponse(content="Synthesis", model=self.model_name)
        return LLMResponse(content="worker-result", model=self.model_name)

    def chat_completion_stream(self, *args, **kwargs):
        if False: yield None

    def get_available_models(self):
        return []


def test_team_runtime_executes_dependency_waves_and_outputs_artifact(tmp_path: Path):
    provider = FakeProvider()
    runtime = TeamRuntime(provider, [], workspace=tmp_path)
    result = runtime.run_collect(
        "Perform the assigned task.",
        TeamConfig(
            mode=TeamMode.ANALYSIS,
            max_agents=2,
            parallelism=2,
            max_iterations_per_agent=2,
            output_mode="file",
            output_format="json",
            require_reviewer=True,
        ),
    )
    assert result.success
    assert len(result.agents) == 2
    assert result.artifact_paths
    artifact = Path(result.artifact_paths[0])
    assert artifact.exists()
    assert artifact.suffix == ".json"
    assert '"team_id"' in artifact.read_text(encoding="utf-8")


def test_agent_profiles_support_distinct_provider_selector(tmp_path: Path):
    primary = FakeProvider("primary")
    alternate = FakeProvider("alternate")
    profile = AgentProfile(
        role_id="verifier",
        name="Verifier",
        profession="Verifier",
        mission="Verify",
        instructions="Verify independently",
        model_role="alternate",
    )
    runtime = TeamRuntime(
        primary,
        [],
        workspace=tmp_path,
        provider_selector=lambda p: alternate if p.model_role == "alternate" else primary,
    )
    assert runtime._provider_for(profile) is alternate


def test_mcp_tools_are_exposed_to_mcp_roles(tmp_path):
    from nexus_agent.team.store import TeamStore
    from nexus_agent.team.runtime import TeamRuntime

    class ExternalTool:
        name = "calendar_search"
        is_mcp = True

    store = TeamStore(tmp_path / "teams.db")
    runtime = TeamRuntime(
        FakeProvider(),
        [ExternalTool()],
        workspace=tmp_path,
    )
    profile = AgentProfile(
        role_id="researcher",
        name="Researcher",
        profession="Researcher",
        mission="Research",
        instructions="Research",
        tool_categories=["read", "mcp"],
    )
    tools = runtime._tools_for(profile, store, "team-1")
    assert any(getattr(tool, "is_mcp", False) for tool in tools)
    store.close()

    
def test_builtin_profiles_are_not_auto_loaded_as_saved_agents(tmp_path: Path):
    from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec
    from nexus_agent.llm.base import LLMProvider
    from nexus_agent.team.runtime import TeamRuntime

    registry = AgentRegistry(tmp_path, project_root=tmp_path)
    user_spec = AgentSpec(
        id="user-reviewer",
        name="User Reviewer",
        profession="Reviewer",
        description="",
        mission="Review user tasks",
        instructions="Review carefully",
        scope=AgentScope.USER,
        tool_categories=["read"],
        reviewer=True,
    )
    registry.save(user_spec, AgentScope.USER)
    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path, agent_registry=registry)
    saved = [
        spec for spec in registry.load()
        if getattr(spec.scope, "value", spec.scope) != "builtin"
    ]
    assert any(spec.id == "user-reviewer" for spec in saved)


def test_team_runtime_markdown_artifact_serializes_quality_gate(tmp_path: Path):
    provider = FakeProvider()
    runtime = TeamRuntime(provider, [], workspace=tmp_path)
    result = runtime.run_collect(
        "Perform the assigned task and produce a report.",
        TeamConfig(
            mode=TeamMode.ANALYSIS,
            max_agents=2,
            parallelism=2,
            max_iterations_per_agent=2,
            output_mode="file",
            output_format="markdown",
            require_reviewer=True,
        ),
    )
    assert result.success
    artifact = Path(result.artifact_paths[0])
    content = artifact.read_text(encoding="utf-8")
    assert "## Evidence Quality Gate" in content
    assert "{}" in content


def test_unknown_dependency_is_failed_before_worker_submission(tmp_path, monkeypatch):
    from nexus_agent.team import AgentProfile, TeamConfig, TeamMode
    import nexus_agent.team.runtime as runtime_module

    profiles = [
        AgentProfile(
            role_id="blocked",
            name="Blocked",
            profession="Blocked Worker",
            mission="Must not execute",
            instructions="Must not execute",
            tool_categories=["read"],
            dependencies=["missing"],
        ),
        AgentProfile(
            role_id="independent",
            name="Independent",
            profession="Independent Worker",
            mission="Execute normally",
            instructions="Execute normally",
            tool_categories=["read"],
        ),
    ]
    monkeypatch.setattr(
        runtime_module,
        "generate_team",
        lambda provider, goal, config, saved_agents=None: (TeamMode.ANALYSIS, profiles),
    )

    result = TeamRuntime(FakeProvider(), [], workspace=tmp_path).run_collect(
        "Run the team.",
        TeamConfig(
            mode=TeamMode.ANALYSIS,
            max_agents=2,
            parallelism=2,
            max_iterations_per_agent=1,
            auto_synthesize=False,
            require_reviewer=False,
        ),
    )

    blocked = next(item for item in result.agents if item["agent_id"] == "blocked")
    assert blocked["status"] == "failed"
    assert "Unknown dependency: missing" in blocked["error"]
    assert result.success is False


def test_read_only_specialists_can_coordinate_and_read_safe_state(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="researcher",
        name="Researcher",
        profession="Researcher",
        mission="Research",
        instructions="Research",
        tool_categories=["read"],
        write_access=False,
    )
    config = TeamConfig(mode=TeamMode.ANALYSIS)
    for name, arguments in (
        ("team_send_message", {"message": "finding"}),
        ("team_read_messages", {}),
        ("memory_scoped", {"action": "search"}),
        ("memory_scoped", {"action": "stats"}),
        ("todowrite", {"action": "list"}),
        ("todowrite", {"action": "get", "todo_id": "x"}),
    ):
        call = ToolCall(id="test", name=name, arguments=arguments)
        assert runtime._permission(call, config, profile, []) is True


def test_read_only_specialists_cannot_mutate_stateful_tools(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="researcher",
        name="Researcher",
        profession="Researcher",
        mission="Research",
        instructions="Research",
        tool_categories=["read"],
        write_access=False,
    )
    config = TeamConfig(mode=TeamMode.ANALYSIS)
    for name, arguments in (
        ("memory_scoped", {"action": "store", "content": "x"}),
        ("memory_scoped", {"action": "forget", "entry_id": "x"}),
        ("todowrite", {"action": "add", "content": "x"}),
        ("todowrite", {"action": "clear_all"}),
    ):
        call = ToolCall(id="test", name=name, arguments=arguments)
        assert runtime._permission(call, config, profile, []) is False


def test_delegate_category_enables_boomerang_without_code_write_access(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="delegator",
        name="Delegator",
        profession="Coordinator",
        mission="Delegate",
        instructions="Delegate",
        tool_categories=["read", "delegate"],
        write_access=False,
    )
    call = ToolCall(id="test", name="boomerang", arguments={"action": "list_tasks"})
    assert runtime._permission(call, TeamConfig(mode=TeamMode.ANALYSIS), profile, []) is True


def test_read_only_tools_remain_available_to_team_specialists(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall
    from nexus_agent.tools.git_ops import SmartCommitTool

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="analyst",
        name="Analyst",
        profession="Analyst",
        mission="Analyze",
        instructions="Analyze",
        tool_categories=["read", "git"],
        write_access=False,
    )
    config = TeamConfig(mode=TeamMode.ANALYSIS)

    for name, arguments in (
        ("smart_commit", {}),
        ("git", {"subcommand": "status"}),
        ("git", {"subcommand": "diff"}),
        ("git", {"subcommand": "log"}),
    ):
        tool = SmartCommitTool(tmp_path) if name == "smart_commit" else type(
            "Tool",
            (),
            {"name": name, "permission_level": "read-only" if name == "smart_commit" else "read-write"},
        )()
        assert runtime._permission(
            ToolCall(id="test", name=name, arguments=arguments),
            config,
            profile,
            [tool],
        ) is True


def test_read_only_team_specialist_cannot_mutate_git(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="analyst",
        name="Analyst",
        profession="Analyst",
        mission="Analyze",
        instructions="Analyze",
        tool_categories=["read", "git"],
        write_access=False,
    )
    config = TeamConfig(mode=TeamMode.ANALYSIS)
    tool = type(
        "Tool",
        (),
        {"name": "git", "permission_level": "read-write"},
    )()
    assert runtime._permission(
        ToolCall(id="test", name="git", arguments={"subcommand": "commit"}),
        config,
        profile,
        [tool],
    ) is False


def test_read_only_team_specialist_cannot_mutate_git_remote(tmp_path: Path):
    from nexus_agent.llm.base import ToolCall

    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    profile = AgentProfile(
        role_id="analyst",
        name="Analyst",
        profession="Analyst",
        mission="Analyze",
        instructions="Analyze",
        tool_categories=["read", "git"],
        write_access=False,
    )
    config = TeamConfig(mode=TeamMode.ANALYSIS)
    tool = type(
        "Tool",
        (),
        {"name": "git", "permission_level": "read-write"},
    )()
    assert runtime._permission(
        ToolCall(id="test", name="git", arguments={"subcommand": "remote", "args": "set-url origin https://example.test"}),
        config,
        profile,
        [tool],
    ) is False
    assert runtime._permission(
        ToolCall(id="test", name="git", arguments={"subcommand": "remote", "args": "-v"}),
        config,
        profile,
        [tool],
    ) is True
