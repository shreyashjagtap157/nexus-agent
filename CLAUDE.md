# NexusAgent — Claude Code Context

## Project
Offline-first AI coding agent running GGUF/ONNX models locally via llama-cpp-python. CLI (Textual) + GUI (FastAPI).

## Commands
- `nexus chat` — Launch CLI TUI
- `nexus gui` — Launch web UI
- `nexus wizard` — First-time setup
- `pip install -e .` — Install from source

## Key Architecture
- `core/agent.py` — AgentLoop (gather→act→verify), configurable effort levels
- `llm/runtime_manager.py` — Runtime orchestration with install/switch/uninstall
- `cli/command_dispatcher.py` — All slash command handlers
- `cli/session_handler.py` — Engine/agent init, interactive model config HUD

## Effort System
5 levels defined in `AgentLoop.EFFORT_CONFIG`:
low(15 iters)→medium(25)→high(50)→xhigh(80)→max(120 iters)
Set via `/effort` command or `CLAUDE_CODE_EFFORT_LEVEL` env var equivalent.

## Testing
`python -m pytest tests/ -v` — 161 tests

## Git
Conventional commits (fix:, feat:, refactor:, docs:). No emoji prefixes.
