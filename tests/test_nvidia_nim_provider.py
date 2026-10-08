from __future__ import annotations

from typing import Any

from nexus_agent.llm.base import Message, Role
from nexus_agent.llm.providers.nvidia_nim_provider import NvidiaNIMProvider


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []
        self.gets = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers, json):
        self.posts.append((url, headers, json))
        return self.responses.pop(0)

    def get(self, url, headers):
        self.gets.append((url, headers))
        return self.responses.pop(0)


def test_nim_provider_polls_202_until_200(monkeypatch):
    client = FakeClient([
        FakeResponse(202, {"requestId": "abc-123"}),
        FakeResponse(202, {"requestId": "abc-123"}),
        FakeResponse(200, {
            "choices": [{
                "message": {"content": "NexusAgent provider test OK"},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 7},
        }),
    ])
    monkeypatch.setattr(
        "nexus_agent.llm.providers.nvidia_nim_provider.httpx.Client",
        lambda **kwargs: client,
    )
    monkeypatch.setattr(
        "nexus_agent.llm.providers.nvidia_nim_provider.time.sleep",
        lambda _: None,
    )

    provider = NvidiaNIMProvider({
        "api_key": "test-key",
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "api_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "pending_poll_seconds": 0.1,
        "pending_max_wait_seconds": 1,
    })
    result = provider.chat_completion([Message(role=Role.USER, content="test")], max_tokens=32)

    assert result.content == "NexusAgent provider test OK"
    assert len(client.posts) == 1
    assert len(client.gets) == 2
    assert client.gets[-1][0].endswith("/status/abc-123")


def test_nim_provider_rejects_202_without_request_id(monkeypatch):
    client = FakeClient([FakeResponse(202, {})])
    monkeypatch.setattr(
        "nexus_agent.llm.providers.nvidia_nim_provider.httpx.Client",
        lambda **kwargs: client,
    )
    provider = NvidiaNIMProvider({"api_key": "test-key"})
    try:
        provider.chat_completion([Message(role=Role.USER, content="test")], max_tokens=8)
    except RuntimeError as exc:
        assert "requestId" in str(exc)
    else:
        raise AssertionError("Expected missing requestId failure")
