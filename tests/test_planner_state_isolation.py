from pathlib import Path

from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ProviderCapabilities
from nexus_agent.team.models import TeamConfig, TeamMode
from nexus_agent.team.planner import generate_team


class FailingProvider(LLMProvider):
    @property
    def name(self): return "test"

    @property
    def model_name(self): return "test"

    def get_capabilities(self):
        return ProviderCapabilities()

    def chat_completion(self, messages, tools=None, temperature=0.1, max_tokens=4096, **kwargs):
        raise RuntimeError("planner unavailable")

    def chat_completion_stream(self, *args, **kwargs):
        if False:
            yield None

    def get_available_models(self):
        return []


def test_builtin_fallback_profiles_are_copied_per_run():
    provider = FailingProvider()
    cfg = TeamConfig(mode=TeamMode.REVIEW, max_agents=3, require_reviewer=True)
    first_mode, first = generate_team(provider, "review", cfg)
    first[-1].reviewer = False
    first[-1].write_access = True
    second_mode, second = generate_team(provider, "review", cfg)
    assert second[-1].reviewer is True
    assert second[-1].write_access is False
