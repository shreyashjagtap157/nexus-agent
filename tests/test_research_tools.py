from pathlib import Path
import hashlib

from nexus_agent.research.tools import ResearchRecordSourceTool
from nexus_agent.team.runtime import TeamRuntime
from nexus_agent.team.models import AgentProfile, TeamConfig, TeamMode
from nexus_agent.llm.base import LLMProvider, ProviderCapabilities


class FakeProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=False,
            supports_streaming=False,
            supports_system_message=True,
            max_context_length=4096,
            max_output_tokens=1024,
        )

    def chat_completion(self, *args, **kwargs):
        raise AssertionError("provider is not used by this test")

    def chat_completion_stream(self, *args, **kwargs):
        yield from ()

    def get_available_models(self):
        return []


def test_research_record_source_fetches_authoritative_content(tmp_path: Path):
    tool = ResearchRecordSourceTool(tmp_path / "research.db", "team-1", "researcher")
    tool.fetcher.execute = lambda url: "authoritative snapshot"

    result = tool.execute(
        url="https://example.test/source",
        title="Example Source",
        content="fabricated content supplied by the worker",
        provider="worker-supplied",
    )

    expected_hash = hashlib.sha256(b"authoritative snapshot").hexdigest()
    assert result["content_hash"] == expected_hash

    with tool.store._connect() as conn:
        row = conn.execute(
            "SELECT content,provider FROM research_sources WHERE source_id=?",
            (result["source_id"],),
        ).fetchone()
    assert row["content"] == "authoritative snapshot"
    assert row["provider"] == "worker-supplied"


def test_user_only_research_does_not_expose_untrusted_source_recorder(tmp_path: Path):
    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    from nexus_agent.team.store import TeamStore

    store = TeamStore(tmp_path / "teams.db")
    try:
        profile = AgentProfile(
            role_id="researcher",
            name="Researcher",
            profession="Researcher",
            mission="Research",
            instructions="Research",
            tool_categories=["read", "research"],
        )
        tools = runtime._tools_for(
            profile,
            store,
            "team-1",
            TeamConfig(
                mode=TeamMode.RESEARCH,
                research_source_strategy="user_only",
            ),
        )
        names = {getattr(tool, "name", "") for tool in tools}
        assert "research_configured_source" in names
        assert "research_record_source" not in names
        assert not names.intersection({"web_search", "web_fetch", "webfetch", "browser"})
    finally:
        store.close()


def test_worker_permission_lookup_uses_dynamically_injected_tools(tmp_path: Path):
    runtime = TeamRuntime(FakeProvider(), [], workspace=tmp_path)
    from nexus_agent.team.store import TeamStore

    store = TeamStore(tmp_path / "teams.db")
    try:
        profile = AgentProfile(
            role_id="researcher",
            name="Researcher",
            profession="Researcher",
            mission="Research",
            instructions="Research",
            tool_categories=["read", "research"],
        )
        tools = runtime._tools_for(
            profile,
            store,
            "team-1",
            TeamConfig(
                mode=TeamMode.RESEARCH,
                research_source_strategy="hybrid",
                auto_approve_tools=False,
            ),
        )
        call = type("ToolCall", (), {"name": "research_record_source"})()
        assert runtime._permission(call, TeamConfig(mode=TeamMode.RESEARCH), profile, tools) is True
    finally:
        store.close()
