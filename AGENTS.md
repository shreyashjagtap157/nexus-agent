# NexusAgent — Agent Context & Memory

## Project Overview
Offline-first AI coding agent that runs GGUF/ONNX LLM models locally via `llama-cpp-python`. Provides CLI (Textual TUI) + GUI (FastAPI) interfaces. Zero internet required by default.

## Quick Start
```bash
pip install -e .
nexus chat                # Launch CLI
nexus gui                 # Launch web UI
nexus wizard              # First-time setup
```

## Architecture
```
src/nexus_agent/
├── core/          # AgentLoop, config, context, sandbox, planner, executor, orchestrator
├── llm/           # Provider interface, LocalEngine (GGUF), OnnxEngine, RuntimeManager, ModelManager
├── cli/           # Textual TUI — app.py (main loop), command_dispatcher.py (slash cmds), wizard.py
├── gui/           # FastAPI web server + static frontend
├── memory/        # SQLite FTS5 memory (working, long-term, episodic, user profile)
├── tools/         # File ops, shell, git, code edit, web search, LSP, browser
├── skills/        # Markdown skill system
├── session/       # Session + checkpoint management
├── permissions/   # Permission gating (suggest/ask/auto)
└── mcp/           # Model Context Protocol
```

## Effort Levels (mapped in `core/agent.py:AgentLoop.EFFORT_CONFIG`)
| Level   | Iterations | Temp | Max Tokens | Reflection |
|---------|-----------|------|------------|------------|
| low     | 15        | 0.30 | 2,048      | No         |
| medium  | 25        | 0.15 | 4,096      | No         |
| high    | 50        | 0.10 | 8,192      | Yes        |
| xhigh   | 80        | 0.05 | 16,384     | Yes        |
| max     | 120       | 0.01 | 32,768     | Yes        |

Set via `/effort [level]` slash command. Config in `agent.effort_level`.

## Runtime Backends (`llm/runtime_manager.py`)
Installable via `/runtime install <backend>`:
- `cpu` — llama-cpp-python CPU (default)
- `cuda` — NVIDIA GPU acceleration
- `vulkan` — Cross-platform GPU
- `metal` — Apple Silicon
- `rocm` — AMD GPU
- `onnx` — ONNX Runtime GenAI

Detection: `cli/runtimes.py` — scans for nvcc, CUDA_PATH, llama-cli, vulkaninfo, etc.

## Key Files
- `core/agent.py` — `AgentLoop` with `run()`/`run_stream()`, tools, reflection, effort config
- `cli/command_dispatcher.py` — All `/cmd` handlers (2317 lines)
- `cli/session_handler.py` — Engine + Agent initialization, model config HUD
- `cli/app.py` — Main REPL loop, mixin orchestration
- `cli/wizard.py` — First-run setup with 7 steps (hardware → runtime → model → permissions → memory → guardrails → cloud)
- `cli/input_handler.py` — Key reading, slash menu, autocomplete
- `cli/renderer.py` — Terminal rendering, TokenUsage, ContextBreakdown, effort/status display
- `llm/runtime_manager.py` — RuntimeManager, SmartRouter, INSTALLABLE_RUNTIMES
- `core/config.py` — Multi-layer config, env var mappings (NEXUS_*)

## Config Env Vars (`core/config.py`)
| Var | Purpose |
|-----|---------|
| `NEXUS_MODELS_DIR` | GGUF model directory |
| `NEXUS_GPU_LAYERS` | GPU offload layers |
| `NEXUS_CONTEXT_SIZE` | Context window |
| `NEXUS_RUNTIME` | Runtime backend (auto/llama-cpp/onnx) |
| `NEXUS_EFFORT_LEVEL` | Reasoning effort |
| `NEXUS_THREADS` | CPU threads |
| `NEXUS_PERMISSION_MODE` | Permission mode |
| `NEXUS_DEFAULT_MODEL` | Default GGUF model path |
| `NEXUS_DEFAULT_PROVIDER` | Cloud provider name |
| `NEXUS_GUI_HOST`/`NEXUS_GUI_PORT` | Web UI binding |

## Known Issues & Fixes Applied
- `STATUS_ILLEGAL_INSTRUCTION` on pre-built wheels → source build with `CMAKE_ARGS="-DLLAMA_NATIVE=ON"`
- `UnicodeEncodeError` on Windows cp1252 → `sys.stdout.reconfigure(encoding='utf-8')` in renderer
- `NameError`/`TypeError` in session_handler, agent_protocol, orchestrator → proper imports + AgentLoopConfig wrapping
- Effort Enter/Esc/mouse in model config HUD → fixed in `_interactive_model_config` (Enter confirms, Esc cancels, mouse clicks parsed)
- Custom GGUF with corrupt header → retrain model (Nemotron 4B works)

## Testing
```bash
python -m pytest tests/ -v
```
161 tests across: memory (35), permissions (18), session (17), cli (14), mcp (8), skills (7), core (8), providers (20).

## Git Convention
- Branch: feature/description
- Emoji-free commit messages
- Conventional commits: "fix:", "feat:", "docs:", "refactor:"
