"""
Backend entry point for the Rust hybrid architecture.

Spawned by the Rust CLI binary (`nexus chat`). Runs the agent
initialization then accepts ACP JSON-RPC 2.0 commands over stdin/stdout.

Usage:
    python -m nexus_agent.backend --acp --workspace /path
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.WARNING,
    format="[backend] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the ACP backend."""
    parser = argparse.ArgumentParser(description="Nexus Agent ACP Backend")
    parser.add_argument("--acp", action="store_true", help="Run as ACP stdio backend")
    parser.add_argument(
        "--workspace",
        type=str,
        default=".",
        help="Working directory for the agent",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to GGUF model or model alias",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Provider to use (local, anthropic, openai, etc.)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Initialize and report status, then exit (for doctor)",
    )
    return parser.parse_args(argv)


def _create_mock_provider():
    """Create a minimal mock provider for dry-run or fallback."""
    from nexus_agent.llm.base import LLMProvider, LLMResponse, Message, ToolDefinition
    from collections.abc import Iterator

    class MockProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "mock"
        @property
        def model_name(self) -> str:
            return "mock-model"
        def get_capabilities(self) -> dict[str, Any]:
            return {"max_context": 4096, "supports_streaming": True}
        def get_available_models(self) -> list[dict[str, Any]]:
            return [{"name": "mock-model", "provider": "mock"}]
        def chat_completion(
            self,
            messages: list[Message],
            tools: list[ToolDefinition] | None = None,
            temperature: float = 0.1,
            max_tokens: int = 4096,
            **kwargs: Any,
        ) -> LLMResponse:
            return LLMResponse(content="Mock response")
        def chat_completion_stream(
            self,
            messages: list[Message],
            tools: list[ToolDefinition] | None = None,
            temperature: float = 0.1,
            max_tokens: int = 4096,
            **kwargs: Any,
        ) -> Iterator[Any]:
            chunk = type("Chunk", (), {"content": "Mock", "tool_calls": None, "usage": None, "is_final": False})
            yield chunk()
            yield chunk()
        def close(self) -> None:
            pass

    return MockProvider()


def _init_agent(workspace: Path, model: str | None, provider: str | None) -> Any:
    """
    Initialize the agent loop with all subsystems.

    This mirrors the initialization in SessionOrchestratorMixin._initialize()
    but runs standalone without a TUI or NexusApp instance.
    """
    from nexus_agent.core.config import load_config
    from nexus_agent.core.agent import AgentLoop, AgentLoopConfig

    # 1. Load config
    config = load_config(workspace=workspace)
    agent_cfg = config.setdefault("agent", {})
    if provider:
        agent_cfg["provider"] = provider
    if model:
        agent_cfg["default_model"] = model

    # 2. Initialize memory
    from nexus_agent.memory.memory_manager import MemoryManager
    memory_data_dir = config.get("data_dir", "~/.nexus-agent/memory")
    memory = MemoryManager(data_dir=memory_data_dir)

    # 3. Initialize session (creates or resumes)
    from nexus_agent.session.manager import SessionManager
    session_data_dir = config.get("data_dir", "~/.nexus-agent/sessions")
    session_mgr = SessionManager(data_dir=session_data_dir)

    # 4. Create tool registry
    from nexus_agent.tools.file_ops import (
        ReadFileTool,
        WriteFileTool,
        ListDirectoryTool,
        SearchFilesTool,
    )
    from nexus_agent.tools.shell import ShellTool
    from nexus_agent.tools.code_edit import CodeEditTool
    from nexus_agent.tools.web_search import WebSearchTool
    from nexus_agent.tools.webfetch import WebFetchTool
    from nexus_agent.tools.todowrite import TodoWriteTool
    from nexus_agent.tools.memory import MemoryTool
    from nexus_agent.tools.boomerang import BoomerangTool
    from nexus_agent.tools.council import CouncilTool

    boomerang_tool = BoomerangTool()
    council_tool = CouncilTool()

    tools: list[Any] = [
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        ListDirectoryTool(workspace),
        SearchFilesTool(workspace),
        CodeEditTool(workspace),
        ShellTool(workspace),
        WebSearchTool(),
        WebFetchTool(),
        TodoWriteTool(),
        MemoryTool(memory),
        boomerang_tool,
        council_tool,
    ]

    # 5. Determine provider
    provider_name = provider or config.get("agent", {}).get("provider", "local")
    model_path = model or config.get("agent", {}).get("default_model")

    if model_path or provider_name != "local":
        # User specified a model or a cloud provider — create a real provider
        from nexus_agent.llm.providers.factory import ProviderFactory
        llm_provider = ProviderFactory.create_provider(
            provider_name, config, model_path
        )
        if llm_provider is None:
            raise RuntimeError(
                f"Provider '{provider_name}' could not be initialized. "
                "Check your config and ensure the model exists."
            )
    else:
        # No model and no provider specified — use a mock provider for
        # dry-run / doctor mode. Real usage requires a model or provider.
        logger.warning(
            "No model or provider specified — using mock provider. "
            "Set --model or --provider for real agent operation."
        )
        llm_provider = _create_mock_provider()

    # 6. Create agent config (config-only fields — provider/tools are passed separately)
    agent_cfg_obj = AgentLoopConfig(
        workspace=workspace,
    )

    # 7. Create agent loop
    agent = AgentLoop(
        provider=llm_provider,
        tools=tools,
        config=agent_cfg_obj,
    )

    # 8. Late-bind agent loop and provider to tools that need them
    agent.memory = memory
    boomerang_tool.set_agent_loop(agent)
    council_tool.set_provider(llm_provider)
    return agent


def _create_agent_factory(workspace: Path, model: str | None, provider: str | None):
    """
    Create an async factory function that initializes an agent.

    Returns an async callable suitable for use as ACPServer's agent_factory.
    """
    agent_instance = None

    async def factory():
        nonlocal agent_instance
        if agent_instance is not None:
            return agent_instance
        logger.info("Initializing agent (workspace=%s, model=%s, provider=%s)",
                     workspace, model, provider)
        try:
            agent_instance = _init_agent(workspace, model, provider)
            logger.info("Agent initialized successfully")
            return agent_instance
        except Exception as e:
            logger.error("Agent initialization failed: %s", e, exc_info=True)
            raise

    return factory


def run_acp_backend(args: argparse.Namespace) -> None:
    """Run the ACP backend server."""
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        logger.error("Workspace does not exist: %s", workspace)
        sys.exit(1)

    os.chdir(workspace)

    # Create agent factory
    agent_factory = _create_agent_factory(workspace, args.model, args.provider)

    # Create and run the ACP server
    from nexus_agent.mcp.acp_server import ACPServer

    server = ACPServer(agent_factory=agent_factory, workspace=workspace)

    # Run the async event loop
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl+C)")
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


def main() -> None:
    """Entry point for python -m nexus_agent.backend."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.acp:
        print("Usage: python -m nexus_agent.backend --acp [options]")
        sys.exit(1)

    if args.dry_run:
        # Test initialization only, don't run the server
        workspace = Path(args.workspace).resolve()
        if not workspace.exists():
            print(f"ERROR: Workspace does not exist: {workspace}")
            sys.exit(1)
        try:
            agent = _init_agent(workspace, args.model, args.provider)
            print(f"OK Agent initialized (session={agent.session_id})")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        return

    run_acp_backend(args)


if __name__ == "__main__":
    main()
