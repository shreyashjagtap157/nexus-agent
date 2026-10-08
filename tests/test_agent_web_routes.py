from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_agent.agents.models import AgentScope, AgentSpec
from nexus_agent.agents.web_routes import register_agent_routes


class _State(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _Provider:
    name = "test"
    model_name = "test-model"


def test_agent_generate_route_initializes_provider_for_local_request(tmp_path: Path, monkeypatch):
    app = FastAPI()
    state = _State(workspace=str(tmp_path), config={"providers": {"active": "local"}}, engine=_Provider())
    register_agent_routes(app, state)

    spec = AgentSpec(
        id="generated-reviewer",
        name="Generated Reviewer",
        profession="Reviewer",
        description="",
        mission="Review",
        instructions="Review independently.",
        scope=AgentScope.WORKSPACE,
    )
    monkeypatch.setattr(
        "nexus_agent.agents.web_routes.AgentGenerator.generate",
        lambda self, request, max_agents=6: [spec],
    )

    response = TestClient(app).post(
        "/api/agents/generate",
        json={
            "request": "Create a reviewer",
            "max_agents": 1,
            "scope": "workspace",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agents"][0]["id"] == "generated-reviewer"
    assert (tmp_path / ".nexus-agent" / "agents" / "generated-reviewer.md").exists()
