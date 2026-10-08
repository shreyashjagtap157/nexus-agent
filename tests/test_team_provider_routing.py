from nexus_agent.team.models import AgentProfile
from nexus_agent.team.providers import make_provider_selector


def test_agent_provider_fallbacks_can_select_distinct_models(monkeypatch):
    created = []

    class FakeProvider:
        def __init__(self, provider, model):
            self._provider = provider
            self._model = model

        @property
        def name(self):
            return self._provider

        @property
        def model_name(self):
            return self._model or self._provider

        def close(self):
            return None

    def fake_create(name, config, model=None):
        value = FakeProvider(name, model)
        created.append(value)
        return value

    monkeypatch.setattr(
        "nexus_agent.team.providers.ProviderFactory.create_provider",
        staticmethod(fake_create),
    )

    selector = make_provider_selector({}, FakeProvider("default", "default-model"))
    profile = AgentProfile(
        role_id="researcher",
        name="Researcher",
        profession="Researcher",
        mission="Research",
        instructions="Research carefully",
        provider="primary",
        model="model-a",
        fallbacks=["secondary/model-b", "tertiary"],
    )
    selected = selector(profile)

    assert selected.name == "primary->secondary->tertiary"
    assert selected.primary.model_name == "model-a"
    assert [item.model_name for item in selected._fallbacks] == ["model-b", "tertiary"]


def test_primary_provider_initialization_failure_falls_back(monkeypatch):
    class FakeProvider:
        def __init__(self, provider, model):
            self._provider = provider
            self._model = model

        @property
        def name(self):
            return self._provider

        @property
        def model_name(self):
            return self._model or self._provider

        def close(self):
            return None

    def fake_create(name, config, model=None):
        if name == "primary":
            raise RuntimeError("primary unavailable")
        return FakeProvider(name, model)

    monkeypatch.setattr(
        "nexus_agent.team.providers.ProviderFactory.create_provider",
        staticmethod(fake_create),
    )

    selector = make_provider_selector({}, FakeProvider("default", "default-model"))
    profile = AgentProfile(
        role_id="researcher",
        name="Researcher",
        profession="Researcher",
        mission="Research",
        instructions="Research carefully",
        provider="primary",
        fallbacks=["secondary/model-b", "tertiary"],
    )
    selected = selector(profile)

    assert selected.name == "secondary->tertiary"
    assert selected.primary.model_name == "model-b"
