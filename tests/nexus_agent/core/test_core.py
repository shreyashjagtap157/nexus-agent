"""Tests for the core agent module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nexus_agent.core.agent import (
    AgentEvent,
    AgentEventType,
    AgentLoop,
    AgentLoopConfig,
    AgentMode,
    AgentState,
    ToolResult,
)
from nexus_agent.llm.base import LLMResponse, Message, Role, ToolCall, ToolDefinition


class TestAgentMode:
    def test_auto_mode(self):
        assert AgentMode.AUTO.value == "auto"

    def test_plan_mode(self):
        assert AgentMode.PLAN.value == "plan"

    def test_build_mode(self):
        assert AgentMode.BUILD.value == "build"

    def test_review_mode(self):
        assert AgentMode.REVIEW.value == "review"

    def test_all_modes(self):
        modes = [m.value for m in AgentMode]
        assert set(modes) == {"auto", "plan", "build", "review"}


class TestAgentState:
    def test_states(self):
        assert AgentState.IDLE.value == "idle"
        assert AgentState.THINKING.value == "thinking"
        assert AgentState.DONE.value == "done"


class TestAgentLoopConfig:
    def test_default_config(self):
        cfg = AgentLoopConfig()
        assert cfg.mode == AgentMode.AUTO
        assert cfg.max_iterations == 50
        assert cfg.temperature == 0.1
        assert cfg.max_tokens == 4096
        assert cfg.effort_level == "medium"

    def test_custom_config(self):
        cfg = AgentLoopConfig(
            mode=AgentMode.PLAN,
            max_iterations=100,
            temperature=0.5,
        )
        assert cfg.mode == AgentMode.PLAN
        assert cfg.max_iterations == 100
        assert cfg.temperature == 0.5

    def test_workspace_default(self):
        cfg = AgentLoopConfig()
        assert cfg.workspace is None


class TestAgentEvent:
    def test_event_creation(self):
        event = AgentEvent(type=AgentEventType.THINKING, data="test")
        assert event.type == AgentEventType.THINKING
        assert event.data == "test"
        assert event.timestamp > 0

    def test_all_event_types(self):
        types = [t.value for t in AgentEventType]
        assert "thinking" in types
        assert "content" in types
        assert "tool_call" in types
        assert "error" in types
        assert "done" in types


class TestToolResult:
    def test_result_creation(self):
        result = ToolResult(
            tool_call_id="tc_1",
            tool_name="test_tool",
            output="result",
            success=True,
        )
        assert result.tool_call_id == "tc_1"
        assert result.success is True

    def test_failed_result(self):
        result = ToolResult(
            tool_call_id="tc_1",
            tool_name="test_tool",
            output="",
            success=False,
            error="Failed",
        )
        assert result.success is False
        assert result.error == "Failed"


class TestAgentLoop:
    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.name = "test"
        provider.model_name = "test-model"
        provider.is_loaded = True
        provider.get_capabilities.return_value = MagicMock(max_context_length=4096)
        provider.count_tokens.return_value = 10
        provider.count_message_tokens.return_value = 100
        provider.get_available_models.return_value = []
        provider.chat_completion.return_value = LLMResponse(
            content="Hello! How can I help?",
            tool_calls=None,
        )
        provider.chat_completion_stream.return_value = iter([
            MagicMock(content="Hello! ", tool_calls=None, usage=None, is_final=False),
            MagicMock(content="How can I help?", tool_calls=None, usage=None, is_final=True),
        ])
        return provider

    @pytest.fixture
    def agent(self, mock_provider):
        config = AgentLoopConfig(
            mode=AgentMode.AUTO,
            workspace=Path("/tmp/test"),
            max_iterations=5,
            temperature=0.1,
            max_tokens=1024,
        )
        return AgentLoop(
            provider=mock_provider,
            tools=[],
            config=config,
        )

    def test_agent_creation(self, agent):
        assert agent is not None
        assert agent.mode == AgentMode.AUTO
        # max_iterations may be overridden by effort level (medium=25)
        assert agent.max_iterations >= 5

    def test_agent_state(self, agent):
        assert agent.state == AgentState.IDLE

    def test_system_prompt(self, agent):
        prompt = agent._build_system_prompt()
        assert "NexusAgent" in prompt
        assert "workspace" in prompt.lower() or "/tmp/test" in prompt

    def test_agent_run(self, agent):
        events = list(agent.run("Hello"))
        assert len(events) > 0
        event_types = [e.type for e in events]
        assert AgentEventType.THINKING in event_types or AgentEventType.DONE in event_types

    def test_agent_stats(self, agent):
        stats = agent.get_stats()
        assert "session_id" in stats
        assert stats["mode"] == "auto"
        assert stats["state"] == "idle"

    def test_clear_history(self, agent):
        agent.messages.append(Message(role=Role.USER, content="test"))
        assert len(agent.messages) == 1
        agent.clear_history()
        assert len(agent.messages) == 0

    def test_effort_levels(self):
        for level in ["low", "medium", "high", "xhigh", "max"]:
            assert level in AgentLoop.EFFORT_CONFIG
            cfg = AgentLoop.EFFORT_CONFIG[level]
            assert "max_iterations" in cfg
            assert "temperature" in cfg
            assert "max_tokens" in cfg
            assert "reflection" in cfg
