from pathlib import Path

from nexus_agent.team import TeamConfig, TeamMode, TeamRuntime
from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ProviderCapabilities


class FakeProvider(LLMProvider):
    def __init__(self):
        self.calls = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-team-model"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=False,
            supports_streaming=True,
            supports_system_message=True,
            max_context_length=32000,
            max_output_tokens=4096,
        )

    def chat_completion(self, messages: list[Message], tools=None, temperature=0.1, max_tokens=4096, **kwargs):
        self.calls += 1
        system = messages[0].content if messages else ""
        if system and "team architect" in system.lower():
            return LLMResponse(
                content='{"agents":['
                        '{"name":"Architect","profession":"Software Architect","mission":"Design the solution","instructions":"Inspect and plan","tool_categories":["read"],"write_access":false,"reviewer":false},'
                        '{"name":"Implementer","profession":"Implementation Engineer","mission":"Implement the solution","instructions":"Make the required change","tool_categories":["read","write"],"write_access":true,"reviewer":false},'
                        '{"name":"Reviewer","profession":"Code Reviewer","mission":"Review the result","instructions":"Independently inspect the result","tool_categories":["read"],"write_access":false,"reviewer":true}'
                        ']}',
                model=self.model_name,
            )
        if system and "integration lead" in system.lower():
            return LLMResponse(content="Integrated team result.", model=self.model_name)
        return LLMResponse(content="TASK COMPLETE: worker finished its assigned objective.", model=self.model_name)

    def chat_completion_stream(self, messages: list[Message], tools=None, temperature=0.1, max_tokens=4096, **kwargs):
        yield from ()

    def get_available_models(self):
        return [{"id": self.model_name, "name": self.model_name, "provider": self.name}]


def test_team_runtime_executes_real_agent_loops_in_parallel(tmp_path: Path):
    provider = FakeProvider()
    runtime = TeamRuntime(provider=provider, tools=[], workspace=tmp_path)
    result = runtime.run_collect(
        "Inspect this project and produce a verified result.",
        TeamConfig(
            mode=TeamMode.CODE,
            max_agents=3,
            parallelism=3,
            max_iterations_per_agent=3,
            workspace=str(tmp_path),
            require_reviewer=True,
            auto_synthesize=True,
            auto_approve_tools=False,
        ),
    )

    assert result.success is True
    assert result.team_id
    assert len(result.agents) == 3
    assert sum(a["status"] == "completed" for a in result.agents) == 3
    assert result.synthesis == "Integrated team result."
    assert provider.calls >= 5


def test_team_runtime_persists_blackboard_messages(tmp_path: Path):
    provider = FakeProvider()
    runtime = TeamRuntime(provider=provider, tools=[], workspace=tmp_path)
    result = runtime.run_collect(
        "Analyze this task.",
        TeamConfig(
            mode=TeamMode.ANALYSIS,
            max_agents=2,
            parallelism=2,
            max_iterations_per_agent=2,
            workspace=str(tmp_path),
        ),
    )

    from nexus_agent.team.store import TeamStore

    store = TeamStore(tmp_path / ".nexus" / "teams.db")
    try:
        messages = store.messages(result.team_id)
        assert any(m["message_type"] == "TASK_ASSIGNMENT" for m in messages)
        assert any(m["message_type"] == "COMPLETION" for m in messages)
        assert any(m["message_type"] == "TEAM_COMPLETE" for m in messages)
        assert store.team(result.team_id)["status"] == "completed"
    finally:
        store.close()

    
def test_team_roles_do_not_collide_between_runs(tmp_path: Path):
    provider = FakeProvider()
    runtime = TeamRuntime(provider=provider, tools=[], workspace=tmp_path)
    cfg = TeamConfig(mode=TeamMode.ANALYSIS, max_agents=2, parallelism=2, max_iterations_per_agent=2)
    first = runtime.run_collect("Analyze task one.", cfg)
    second = runtime.run_collect("Analyze task two.", cfg)

    from nexus_agent.team.store import TeamStore

    store = TeamStore(tmp_path / ".nexus" / "teams.db")
    try:
        first_agents = store.agents(first.team_id)
        second_agents = store.agents(second.team_id)
        assert len(first_agents) == len(second_agents) == 2
        assert {a["agent_id"] for a in first_agents}.isdisjoint({a["agent_id"] for a in second_agents})
    finally:
        store.close()
