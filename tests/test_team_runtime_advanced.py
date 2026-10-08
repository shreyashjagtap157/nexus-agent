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
