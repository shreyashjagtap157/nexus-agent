import pytest

from nexus_agent.workflows import WorkflowRegistry
from nexus_agent.team.models import TeamMode


def test_named_workflows_are_resolvable():
    registry = WorkflowRegistry()
    ids = {item.id for item in registry.list()}
    assert {"code-change", "research-verify", "exhaustive-research", "repository-audit"} <= ids
    assert registry.get("code-change").mode == TeamMode.CODE
    assert registry.get("research-verify").research_depth == "comprehensive"


def test_unknown_workflow_is_rejected():
    with pytest.raises(ValueError):
        WorkflowRegistry().get("does-not-exist")
