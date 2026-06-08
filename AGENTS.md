# NexusAgent — Agent Context & Memory

## Project Overview
Offline-first AI coding agent that runs GGUF/ONNX LLM models locally via `llama-cpp-python`. Provides a high-fidelity inline REPL CLI (TUI) and a FastAPI GUI interface. Zero internet required by default.

## Quick Start
```bash
pip install -e .
nexus chat                # Launch CLI
nexus gui                 # Launch web UI
nexus wizard              # First-time setup
```

## TUI Design
The CLI is implemented as a **high-fidelity inline REPL**. Unlike modal-based interfaces, it maintains a continuous flow where the prompt is integrated into the terminal stream, matching the interaction model of tools like Claude Code. It uses a custom raw-mode input handler to support real-time autocomplete, slash-command menus, and interactive rendering without breaking the terminal scrollback.

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
| Level   | Iterations | Temp | Max Tokens | Reflection | Multi-Pass |
|---------|-----------|------|------------|------------|------------|
| low     | 15        | 0.30 | 2,048      | No         | No         |
| medium  | 25        | 0.15 | 4,096      | No         | No         |
| high    | 50        | 0.10 | 8,192      | Yes        | No         |
| xhigh   | 80        | 0.05 | 16,384     | Yes        | Yes        |
| max     | 120       | 0.01 | 32,768     | Yes        | Yes        |

Multi-pass (xhigh+): automatic planning prompt injected before execution, final review pass after completion.

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
- `cli/command_dispatcher.py` — All `/cmd` handlers (includes dynamic plugin dispatch)
- `cli/session_handler.py` — Engine + Agent initialization, model config HUD
- `cli/app.py` — Main REPL loop, mixin orchestration
- `cli/wizard.py` — First-run setup with 7 steps (hardware → runtime → model → permissions → memory → guardrails → cloud)
- `cli/input_handler.py` — Key reading, slash menu, autocomplete
- `cli/renderer.py` — Terminal rendering, TokenUsage, ContextBreakdown, effort/status display
- `llm/runtime_manager.py` — RuntimeManager, SmartRouter, INSTALLABLE_RUNTIMES
- `core/config.py` — Multi-layer config, env var mappings (NEXUS_*)
- `core/usage.py` — Token usage and cost tracking (JSON-backed)
- `core/plugins.py` — Dynamic plugin loading (commands & tools)
- `mcp/acp_server.py` — JSON-RPC stdio server for external control

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
726 tests across: memory, permissions, session, cli, mcp, skills, core, providers, usage, plugins.

## Git Convention
- Branch: feature/description
- Emoji-free commit messages
- Conventional commits: "fix:", "feat:", "docs:", "refactor:"

### Pre-commit Hook
Location: `.githooks/pre-commit`
Enable: `git config core.hooksPath .githooks`

Runs full test suite on every commit. Updates ``docs/exhaustive_audit.md``
and ``docs/FRESH_AUDIT.md`` with current test counts and verification date,
then stages both files. Aborts commit if any test fails.

Flags:
- ``--from-file <path>`` — read pre-existing pytest output instead of running
  tests (for CI workflows that run tests separately).
- ``--ci`` — label audit as "verified via CI" and skip ``git add``.

Test args: ``-q --tb=short -W error::ResourceWarning`` (promotes unclosed
resource warnings to errors).

## CI Workflow (`.github/workflows/test-and-audit.yml`)

| Detail | Value |
|--------|-------|
| Name | ``Test & Audit`` |
| Triggers | ``push`` to ``main``/``master``, ``pull_request`` to ``main``/``master``, ``workflow_dispatch`` |
| Runner | ``ubuntu-latest`` (Python 3.12) |

Steps:
1. Checkout with full git history (``fetch-depth: 0``).
2. Install dependencies via ``pip install -e ".[dev]"``.
3. **Run tests** — ``python -m pytest tests/ -q --tb=short > pytest_output.txt``
4. **Update audit docs** — runs the pre-commit hook in CI mode:
   ``python .githooks/pre-commit --from-file pytest_output.txt --ci``
5. **Auto-commit audit updates** (on push to main/master or workflow_dispatch)
   — commits ``docs/exhaustive_audit.md`` and ``docs/FRESH_AUDIT.md`` with
   message ``docs: auto-update audit with latest test results`` and pushes.
6. **Upload pytest output** — uploaded as artifact for debugging.
