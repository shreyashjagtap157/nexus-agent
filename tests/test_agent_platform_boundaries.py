from pathlib import Path

from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec
from nexus_agent.auth import AuthStore
from nexus_agent.llm.base import LLMProvider, ProviderCapabilities
from nexus_agent.storage.layout import StorageLayout
from nexus_agent.team.models import AgentProfile
from nexus_agent.team.providers import make_provider_selector
from nexus_agent.tools.file_ops import DeleteFileTool, RestoreFileTool


class StubProvider(LLMProvider):
    @property
    def name(self): return "stub"

    @property
    def model_name(self): return "stub-model"

    def get_capabilities(self):
        return ProviderCapabilities(
            supports_tool_calling=False,
            supports_streaming=False,
            supports_system_message=True,
            max_context_length=4096,
            max_output_tokens=512,
        )

    def chat_completion(self, *args, **kwargs):
        raise RuntimeError("not used")

    def chat_completion_stream(self, *args, **kwargs):
        if False:
            yield None

    def get_available_models(self):
        return []


def test_agent_registry_loads_builtin_and_workspace_profiles(tmp_path: Path):
    workspace_agents = tmp_path / ".nexus-agent" / "agents"
    workspace_agents.mkdir(parents=True)
    custom = AgentSpec(
        id="custom-reviewer",
        name="Custom Reviewer",
        profession="Security Reviewer",
        description="",
        mission="Review security",
        instructions="Inspect dependencies and boundaries.",
        scope=AgentScope.WORKSPACE,
        tool_categories=["read", "search"],
        reviewer=True,
    )
    from nexus_agent.agents.format import write_agent_file
    write_agent_file(workspace_agents / "custom-reviewer.md", custom)

    registry = AgentRegistry(
        workspace=tmp_path,
        global_root=tmp_path / "global",
        user_root=tmp_path / "user",
    )
    loaded = registry.load()
    ids = {item.id for item in loaded}
    assert "architect" in ids
    assert "custom-reviewer" in ids
    assert registry.get("custom-reviewer").scope == AgentScope.WORKSPACE


def test_auth_store_file_backend_never_requires_plaintext_access(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json", backend="file")
    store.set("test-provider", "secret-value")
    assert store.get("test-provider") == "secret-value"
    listing = store.list()
    assert listing[0]["provider"] == "test-provider"
    assert "secret-value" not in str(listing)
    assert store.remove("test-provider") is True
    assert store.get("test-provider") is None


def test_saved_agent_provider_override_wins_over_role_mapping():
    default = StubProvider()
    profile = AgentProfile(
        role_id="verifier",
        name="Verifier",
        profession="Verifier",
        mission="Verify",
        instructions="Verify",
        model_role="reviewer",
        provider="custom",
        model="custom-model",
        fallbacks=["nvidia_nim"],
    )
    selector = make_provider_selector(
        {
            "team": {
                "roles": {
                    "reviewer": {
                        "provider": "openai",
                        "model": "mapped-model",
                        "fallbacks": ["groq"],
                    }
                }
            }
        },
        default,
    )
    selected = selector(profile)
    assert selected.name == "custom"


def test_delete_and_restore_file_round_trip(tmp_path: Path):
    target = tmp_path / "example.txt"
    target.write_text("restore me", encoding="utf-8")
    deleter = DeleteFileTool(tmp_path)
    message = deleter.execute("example.txt")
    assert "NexusAgent trash" in message
    assert not target.exists()

    restore = RestoreFileTool(tmp_path)
    trash_items = restore.execute("list")
    name = next(item for item in trash_items.splitlines() if item)
    result = restore.execute("restore", trash_name=name, destination="example.txt")
    assert "Restored" in result
    assert target.read_text(encoding="utf-8") == "restore me"


def test_storage_layout_is_explicit(tmp_path: Path):
    layout = StorageLayout(tmp_path)
    assert layout.workspace_runtime == tmp_path / ".nexus-agent" / "runtime"
    assert layout.auth_file.name == "auth.json"
