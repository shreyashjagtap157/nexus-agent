# NexusAgent — Agent Context & Memory

## Project Overview
Local-first multi-agent development and research workbench. The shared runtime supports single-agent workflows, dynamically assembled teams, evidence-first research, provider routing, scoped memory, web/MCP tools, a web console, a Rust client and a native desktop client. Local inference remains a first-class capability, while hosted/custom providers are supported.

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

The authoritative validation surface is GitHub Actions. The complete Python test suite runs across supported Python versions and Ubuntu, Windows and macOS. Separate workflows validate Ruff/MyPy, native Rust clients, version synchronization, audit evidence and security/dependency checks.

For the local development loop, run:

```bash
python -m pytest tests/ -q
python -m ruff check src/
python -m ruff format --check src/
python -m mypy src/nexus_agent/
python scripts/check_version.py
```

## Git Convention
- Canonical integration branch: main
- Work through pull requests; do not push directly to main
- Use short-lived feature branches with descriptive names
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

## CI Workflow (.github/workflows/ci.yml)

The authoritative pull-request validation workflow is a single CI run with a deterministic Required aggregation job.

| Detail | Value |
|--------|-------|
| Name | CI |
| Triggers | push to main, pull_request to main, workflow_dispatch |
| Required merge gate | Required |

Validation includes:

1. Complete Python tests on Ubuntu, Windows and macOS for Python 3.10–3.13.
2. Ruff formatting/linting and MyPy.
3. Rust formatting and compilation for both native clients on all supported operating systems.
4. Repository version-contract validation.
5. Canonical pytest evidence and read-only audit artifacts.
6. A final Required job that fails unless every CI component succeeds.

The separate .github/workflows/security.yml workflow provides CodeQL, dependency auditing and dependency review.

CI workflows are intentionally read-only and never push commits to protected integration branches.
