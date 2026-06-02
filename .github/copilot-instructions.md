# NexusAgent — GitHub Copilot Instructions

## Project Context
NexusAgent is an offline-first AI coding agent in Python. It loads GGUF/ONNX LLM models locally via `llama-cpp-python`.

## Key Files
- `src/nexus_agent/core/agent.py` — Main agent loop with effort levels
- `src/nexus_agent/llm/runtime_manager.py` — Runtime install/switch/uninstall
- `src/nexus_agent/cli/command_dispatcher.py` — Slash commands
- `src/nexus_agent/cli/session_handler.py` — Engine/agent initialization

## Conventions
- Python 3.10+, type hints everywhere
- `__future__ import annotations` at top
- Mixin-based class composition for CLI
- No emoji in commit messages, conventional commits
