# NexusAgent — Project Context & Continuation Guide

> **Last Updated:** 2026-05-31
> **Project Root:** `D:/Project/nexus-agent/`
> **Language:** Python 3.10+
> **Status:** Phase A-E Fully Complete — Production-ready v1.0

---

## 1. PROJECT OVERVIEW

**NexusAgent** is an **offline-first, local-LLM-powered AI coding agent** that provides both a CLI (TUI) and GUI interface. The key differentiator from all existing agents (claude-code, opencode, codex, etc.) is that it **loads and runs GGUF LLM models directly on the user's machine** via `llama-cpp-python`, requiring zero internet connectivity by default.

### 1.1 Design Philosophy

| Principle | Description |
|:---|:---|
| **Offline-First** | Local GGUF model hosting is the default. Cloud providers are optional add-ons. |
| **Provider-Agnostic** | Unified `LLMProvider` interface — swap between local/cloud with one config change. |
| **Agentic Loop** | Gather → Act → Verify cycle (from claude-code/codex pattern). |
| **Persistent Memory** | Agent remembers across sessions (from letta/hermes pattern). |
| **Dual Interface** | Rich terminal TUI (Textual) + web-based GUI (FastAPI). |
| **Permission-Gated Tools** | Every tool action goes through permission checks (allow/ask/deny). |
| **Modular Skills** | Markdown-based skill system (from openclaw/hermes pattern). |

### 1.2 Inspiration Sources & What We Took

| Source Project | What We Adopted | Where It Lives |
|:---|:---|:---|
| **claude-code** | Agentic loop (gather→act→verify), checkpoint/rollback, `/rewind`, streaming, CLAUDE.md-style config | `core/agent.py`, `session/checkpoint.py` |
| **opencode** | Provider abstraction layer (75+ providers), Plan/Build agent modes, TUI layout, auto-compact, LSP integration, permission model (allow/ask/deny) | `llm/base.py`, `llm/providers/`, `core/planner.py`, `core/executor.py`, `permissions/` |
| **openclaw** | Skill system via Markdown SKILL.md files, heartbeat scheduler, multi-channel gateway pattern, web control UI | `skills/`, built-in skill `.md` files |
| **letta (MemGPT)** | Persistent stateful memory, agent self-edits memory, working/long-term/episodic memory architecture | `memory/` (all files) |
| **jules** | Multi-agent orchestration (planner→executor→tester→reviewer), async background task execution | `core/orchestrator.py` |
| **antigravity-cli** | Sub-agent spawning, parallel task execution, unified agent harness shared between CLI/GUI, bidirectional sync | `core/orchestrator.py`, shared core between `cli/` and `gui/` |
| **hermes agent** | Self-improving learning loop (tasks→skills→memory), user preference profiles, FTS5 memory over SQLite, multi-platform gateway | `memory/user_profile.py`, `memory/long_term.py`, `skills/` |
| **codex (OpenAI)** | Sandboxed execution (Seatbelt/bubblewrap pattern), multimodal support, approval modes (suggest/ask/auto) | `core/sandbox.py` |

### 1.3 What Makes This Project Unique & Premium Capabilities

**No existing agent loads LLM models locally on the machine where the agent itself runs.** All current agents (claude-code, opencode, codex, etc.) connect to cloud APIs. NexusAgent uses `llama-cpp-python` and `onnxruntime-genai` to load GGUF and ONNX models directly into RAM/VRAM/NPU for local execution.

NexusAgent aggregates advanced capabilities from all leading agentic CLIs to provide a premium feature set:
- **Prompt Caching**: Dynamically reuse system prompts, large file context fragments, and tools schemas. This minimizes local evaluation latency and token costs on GGUF and cloud backends.
- **Stateful Memory System**: Leverages a database-backed, multi-tier memory system (working context, SQLite FTS5 long-term recall, conversation episodic store, and YAML-based user profile learning) modeled after MemGPT (letta) and hermes.
- **Multimodal & Vision Processing Support**: Conforms to unified provider interfaces, supporting vision-language local backends (e.g. LLaVA GGUF) and cloud models to parse drawings, schematics, and screenshots directly.
- **Safe Sandbox Command Execution**: Risk-classified sandbox evaluation (suggest/ask/auto) coupled with strict Git Worktree isolation to allow safe, reviewable local workspaces.
- **Extensible Skill Registry**: Custom capabilities load directly from interactive Markdown `.md` sheets, defining dynamic sub-agents for specific coding tasks.


---

## 2. ARCHITECTURE

### 2.1 High-Level Architecture

```
┌──────────────────────────────────────────────────┐
│                    USER                          │
│         (Terminal / Browser / API)               │
└─────────────┬───────────────┬────────────────────┘
              │               │
     ┌────────▼──────┐ ┌──────▼──────┐
     │   CLI (TUI)   │ │  GUI (Web)  │
     │   Textual     │ │  FastAPI    │
     └────────┬──────┘ └──────┬──────┘
              │               │
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │  Agent Core   │
              │  (AgentLoop)  │
              │  + Orchestrator│
              └───┬───┬───┬───┘
                  │   │   │
     ┌────────────┤   │   ├────────────┐
     │            │   │   │            │
┌────▼────┐ ┌────▼───▼┐ ┌▼─────┐ ┌────▼─────┐
│  Tools  │ │   LLM   │ │Memory│ │Sessions  │
│file,git,│ │Backend  │ │System│ │Checkpoint│
│shell,lsp│ │local+   │ │W/LT/ │ │Rollback  │
│edit,web │ │cloud    │ │Ep/UP │ │          │
└─────────┘ └────┬────┘ └──────┘ └──────────┘
                 │
        ┌────────┼────────┐
        │        │        │
   ┌────▼──┐ ┌──▼───┐ ┌──▼────┐
   │Local  │ │Cloud │ │Ollama │
   │Engine │ │APIs  │ │Server │
   │(GGUF) │ │      │ │       │
   └───────┘ └──────┘ └───────┘
```

### 2.2 Directory Structure (Current State)

```
D:/Project/nexus-agent/
├── pyproject.toml                         ✅ Complete
├── .env.example                           ✅ Complete
├── config/
│   └── default.yaml                       ✅ Complete
├── src/nexus_agent/
│   ├── __init__.py                        ✅ Complete
│   ├── __main__.py                        ✅ Complete (CLI entry: nexus chat/gui/model/session/config/hardware/wizard)
│   ├── core/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── config.py                      ✅ Complete (multi-layer config loader)
│   │   ├── agent.py                       ✅ Complete (agentic loop with streaming + tool calling)
│   │   ├── context.py                     ✅ Complete (auto-compaction context manager)
│   │   ├── sandbox.py                     ✅ Complete (sandboxed command execution)
│   │   ├── orchestrator.py                ✅ Complete (Phase 5)
│   │   ├── planner.py                     ✅ Complete (Phase 5)
│   │   ├── executor.py                    ✅ Complete (Phase 5)
│   │   ├── task_graph.py                  ✅ Complete (hierarchical task DAG)
│   │   ├── nla_telemetry.py              ✅ Complete (reasoning telemetry)
│   │   ├── debate.py                      ✅ Complete (multi-agent debate)
│   │   └── devops.py                      ✅ Complete (CI pipeline)
│   ├── llm/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── base.py                        ✅ Complete (LLMProvider interface, Message, ToolCall, etc.)
│   │   ├── local_engine.py                ✅ Complete (llama-cpp-python GGUF engine)
│   │   ├── model_manager.py               ✅ Complete (model discovery, hardware detection)
│   │   └── providers/
│   │       ├── __init__.py                ✅ Complete (Phase 5)
│   │       ├── openai_provider.py         ✅ Complete
│   │       ├── anthropic_provider.py      ✅ Complete
│   │       ├── google_provider.py         ✅ Complete
│   │       ├── ollama_provider.py         ✅ Complete
│   │       ├── openrouter_provider.py     ✅ Complete
│   │       ├── groq_provider.py           ✅ Complete
│   │       ├── deepseek_provider.py       ✅ Complete
│   │       ├── aws_bedrock_provider.py    ✅ Complete
│   │       └── custom_openai_provider.py  ✅ Complete
│   ├── memory/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── memory_manager.py              ✅ Complete (orchestrates all subsystems)
│   │   ├── working_memory.py              ✅ Complete (LRU scratchpad)
│   │   ├── long_term.py                   ✅ Complete (SQLite FTS5 persistent memory)
│   │   ├── episodic.py                    ✅ Complete (session history with FTS5)
│   │   └── user_profile.py               ✅ Complete (YAML-backed preference learning)
│   ├── tools/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── base.py                        ✅ Complete (abstract Tool class)
│   │   ├── file_ops.py                    ✅ Complete (read, write, search, list_directory)
│   │   ├── shell.py                       ✅ Complete (sandboxed command execution)
│   │   ├── code_edit.py                   ✅ Complete (search-replace, insert_lines)
│   │   ├── git_ops.py                     ✅ Complete (git subcommand wrapper)
│   │   ├── web_search.py                  ✅ Complete (DuckDuckGo API)
│   │   ├── lsp_client.py                  ✅ Complete (placeholder — needs language server)
│   │   └── browser.py                     ✅ Complete (placeholder — needs playwright)
│   ├── skills/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── skill_loader.py                ✅ Complete
│   │   ├── skill_registry.py              ✅ Complete
│   │   └── builtin/                       ✅ Complete (builtin code_review.md)
│   ├── mcp/
│   │   ├── __init__.py                    ✅ Complete (Phase 5)
│   │   ├── client.py                      ✅ Complete
│   │   ├── server.py                      ✅ Complete
│   │   └── transport.py                   ✅ Complete
│   ├── session/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── manager.py                     ✅ Complete
│   │   ├── storage.py                     ✅ Complete
│   │   └── checkpoint.py                  ✅ Complete
│   ├── permissions/
│   │   ├── __init__.py                    ✅ Complete
│   │   ├── manager.py                     ✅ Complete
│   │   └── rules.py                       ✅ Complete
│   ├── cli/                               ✅ Complete
│   │   ├── __init__.py
│   │   ├── app.py                         ✅ TUI main application (Textual)
│   │   ├── wizard.py                       ✅ Interactive first-run setup wizard
│   │   ├── auth.py                        ✅ API key management
│   │   ├── renderer.py                    ✅ Rich-based terminal rendering
│   │   ├── theme.py                       ✅ Dark/light theme colors
│   │   ├── file_tree.py                   ✅ Interactive directory tree
│   │   ├── diff_view.py                   ✅ Syntax-highlighted diff viewer
│   │   ├── approval_dialog.py             ✅ Permission approval overlay
│   │   ├── command_dispatcher.py           ✅ Slash command routing
│   │   ├── event_handler.py                ✅ Textual event handling
│   │   ├── input_handler.py               ✅ Input processing
│   │   ├── models_db.py                   ✅ Model database/cache
│   │   ├── runtimes.py                    ✅ Runtime detection
│   │   ├── session_handler.py              ✅ Session integration
│   │   └── styles.tcss                    ✅ Textual CSS styles
│   └── gui/                               ✅ Complete (Phase 4)
│       ├── __init__.py
│       ├── server.py
│       └── frontend/
│           ├── index.html
│           ├── css/styles.css
│           └── js/app.js, chat.js, models.js, settings.js, utils.js
├── tests/                                 ✅ Phase A-E (158 tests)
│   ├── test_imports.py                    ✅ Package import verification
│   ├── test_advanced.py                  ✅ Advanced feature tests
│   ├── test_providers.py                  ✅ Cloud provider tests (20 tests)
│   └── nexus_agent/
│       ├── cli/test_cli.py               ✅ CLI components (14 tests)
│       ├── cli/test_wizard.py            ✅ Setup wizard (3 tests)
│       ├── core/test_core.py             ✅ Config, sqlite_store (8 tests)
│       ├── mcp/test_mcp.py               ✅ MCP client/server/transport (8 tests)
│       ├── memory/test_memory.py          ✅ Memory subsystems (35 tests)
│       ├── permissions/test_permissions.py ✅ Permission system (18 tests)
│       ├── session/test_session.py         ✅ Session/checkpoint (17 tests)
│       └── skills/test_skills.py           ✅ Skill registry (7 tests)
├── docs/
│   ├── CONTEXT.md                         ✅ This file
│   ├── MEMORY.md                          ✅ Implementation memory log
│   ├── ROADMAP.md                         ✅ Detailed execution plan
│   ├── FRESH_AUDIT.md                     ✅ Code quality audit
│   ├── ARCHITECTURE.md                    ✅ System architecture & data flow
│   ├── API.md                             ✅ REST + WebSocket + MCP reference
│   ├── CONTRIBUTING.md                    ✅ Development setup & PR guide
│   ├── SECURITY.md                        ✅ Security model & policy
│   └── examples/                          ✅ Usage guides & tutorials
│       ├── getting_started.md
│       ├── local_models.md
│       ├── cloud_providers.md
│       └── cli_reference.md
└── README.md                              ✅ Comprehensive user guide
```

---

## 3. KEY TECHNICAL DECISIONS

### 3.1 Why Python (not Go/Rust/TypeScript)?

- **Direct `llama-cpp-python` & `onnxruntime-genai` integration** — The primary differentiator (local model hosting) is best served by Python's native bindings to llama.cpp and ONNX Runtime GenAI.
- **Textual framework** — Best-in-class Python TUI framework for the CLI interface (rich rendering, CSS-like styling, event loop).
- **FastAPI** — High-performance async web server for the GUI backend with native WebSocket support.
- **AI/ML ecosystem** — Python has the broadest library support for LLM tooling, tokenizers, and model management.
- **Tradeoff acknowledged:** Go (like opencode) or Rust (like codex) would be faster for CLI startup, but the LLM inference is the bottleneck, not the orchestrator.
- **Tauri v2 Future**: While Tauri v2 (Rust backend + JS frontend) is ideal for native bundles and future iOS deployment, a local FastAPI server allows 100% shared codebase and offline purity.

### 3.2 Why Multi-Runtime Engine Selection?

To support all hardware processors (CPU, GPU, NPU, TPU), we support three local runtimes:
- **llama.cpp (via `llama-cpp-python`)**: Standard default for GGUF models. Outstanding portability, supports CPU and all GPU backends (CUDA, ROCm, Vulkan, Metal, SYCL).
- **ONNX Runtime GenAI**: Standard default for ONNX models. Best-in-class acceleration on Windows NPUs (Qualcomm Hexagon, Intel, AMD) via the WinML/DirectML execution provider.
- **Ollama**: Connects to the local Ollama backend for users who prefer a pre-installed background daemon.
- **TPU (Tensor Processing Unit)**: Note that edge TPUs (e.g. Google Coral) are designed for low-power CNNs with INT8 only and are not viable for local LLM inference. Cloud TPUs are supported as remote backends, but violate the default offline-first policy.

### 3.3 Platform Priority: Windows first -> Linux -> iOS

- **Windows**: The primary OS targeted for local execution, with full PowerShell integration, DirectML NPU support, and a responsive web client.
- **Linux**: Supported with subprocess bash command sandboxing and standard CPU/GPU offloading.
- **iOS**: Supported via network connection from the iOS Safari browser to the local FastAPI web server. A native Tauri app can be compiled in the future as a client package wrapper.

### 3.4 Why SQLite FTS5 (not vector database)?

- **Zero dependencies** — SQLite is built into Python. No external services needed (Chroma, Pinecone, etc.).
- **Offline operation** — No network required for memory search.
- **Good enough** — For code patterns and text recall, keyword-based FTS5 search is sufficient. Vector search would require embedding models, which adds complexity and memory usage.
- **Inspired by hermes agent** — Which uses the same pattern successfully.

### 3.5 Why Textual for CLI (not Bubble Tea)?

- **Same language** — Staying in Python avoids a polyglot codebase. Opencode uses Bubble Tea (Go), but since our core is Python, Textual is the equivalent.
- **Rich ecosystem** — Built on top of Rich library, which provides Markdown rendering, syntax highlighting, tables, and panels out of the box.
- **CSS-like styling** — Textual uses `.tcss` files for styling, enabling premium-looking interfaces.

### 3.6 Why FastAPI for GUI (not Electron/Tauri)?

- **Lightweight** — No Chromium bundle. The GUI runs as a local web server accessed via the user's existing browser.
- **WebSocket native** — Real-time streaming of LLM responses to the browser.
- **Same Python process** — Shares the same agent core, memory, and model with the CLI. No IPC needed.
- **Modern web UI** — HTML/CSS/JS frontend with glassmorphism, dark theme, and responsive design.

---

## 4. IMPLEMENTATION STATUS BY PHASE

### Phase 1: Foundation ✅ COMPLETE
- [x] `pyproject.toml` — Project metadata, dependencies, CLI entry point
- [x] `.env.example` — Environment variable template
- [x] `config/default.yaml` — Full default configuration
- [x] `llm/base.py` — Abstract `LLMProvider` interface with `Message`, `ToolCall`, `ToolDefinition`, `LLMResponse`, `StreamChunk`, `ProviderCapabilities`
- [x] `llm/local_engine.py` — `LocalEngine` class using `llama-cpp-python` with GPU auto-detection, chat format auto-detection, streaming, tool calling
- [x] `llm/model_manager.py` — `ModelManager` with GGUF discovery, metadata extraction, hardware detection, model recommendation
- [x] `core/agent.py` — `AgentLoop` with modes (AUTO/PLAN/BUILD/REVIEW), streaming, tool calling, permission callbacks
- [x] `core/context.py` — `ContextManager` with auto-compaction, tool output trimming
- [x] `core/sandbox.py` — `Sandbox` with risk classification, modes (SUGGEST/ASK/AUTO), command patterns
- [x] `core/config.py` — Multi-layer config loader (default → user → project → env → CLI)
- [x] `__main__.py` — CLI with subcommands: `nexus chat`, `gui`, `model list/info`, `session list/resume`, `config`, `hardware`

### Phase 2: Tools & Memory ✅ COMPLETE
- [x] `tools/base.py` — Abstract `Tool` class with name, description, parameters, permission_level, execute()
- [x] `tools/file_ops.py` — `ReadFileTool`, `WriteFileTool`, `SearchFilesTool`, `ListDirectoryTool`
- [x] `tools/shell.py` — `ShellTool` wrapping `Sandbox`
- [x] `tools/code_edit.py` — `CodeEditTool` (search-replace with diff), `InsertLinesTool`
- [x] `tools/git_ops.py` — `GitTool` with safety checks on dangerous operations
- [x] `tools/web_search.py` — `WebSearchTool` using DuckDuckGo API
- [x] `tools/lsp_client.py` — `LSPClientTool` (placeholder, needs language server integration)
- [x] `tools/browser.py` — `BrowserTool` (placeholder, needs playwright)
- [x] `memory/memory_manager.py` — `MemoryManager` orchestrating all subsystems
- [x] `memory/working_memory.py` — `WorkingMemory` (in-memory LRU scratchpad)
- [x] `memory/long_term.py` — `LongTermMemory` (SQLite FTS5)
- [x] `memory/episodic.py` — `EpisodicMemory` (session history with FTS5)
- [x] `memory/user_profile.py` — `UserProfile` (YAML-backed preference learning)
- [x] `permissions/manager.py` — Permission evaluation engine
- [x] `permissions/rules.py` — Rule definitions
- [x] `session/manager.py` — Session lifecycle management
- [x] `session/storage.py` — SQLite session storage
- [x] `session/checkpoint.py` — Checkpoint/rollback system

### Phase 3: CLI Interface ✅ COMPLETE
All core files in `src/nexus_agent/cli/` have been successfully created, styled, and validated:
- `cli/app.py` — Textual TUI main app coordinating all panels thread-safely
- `cli/file_tree.py` — Interactive `DirectoryTree` sidebar listing workspace files
- `cli/diff_view.py` — Syntax-highlighted unified terminal diff view widget
- `cli/approval_dialog.py` — Pop-up overlay screen (`ApprovalScreen`) blocking and gating agent tool execution
- `cli/theme.py`, `cli/styles.tcss` — Premium dark theming and style overrides mapping layout grids

### Phase 4: GUI Interface ✅ COMPLETE
The local FastAPI-based web server and the premium responsive glassmorphic frontend have been successfully completed:
- `gui/server.py`, `gui/__init__.py` — FastAPI local async server with real-time WebSocket streaming
- `gui/frontend/index.html` — Gorgeous 3-column dashboard structure
- `gui/frontend/css/styles.css` — High-fidelity stylesheet with glow states and transitions
- `gui/frontend/js/` — App, Chat, Models, Settings, and Utils client script controllers

### Phase 5: Advanced Features ✅ COMPLETE
- `skills/` system — ✅ COMPLETE (Implements modular `.md` frontmatter skills loader, registry, built-in code_review executor, and sub-agent loops)
- `core/orchestrator.py`, `core/planner.py`, `core/executor.py` — ✅ COMPLETE (Planner, Executor sub-agents and Orchestrator)
- `mcp/` protocol — ✅ COMPLETE (Stdio transport, Client proxies, Server tool publisher)
- Cloud provider connectors in `llm/providers/` — ✅ COMPLETE (All 9 major cloud connectors implemented via native httpx)

### Phase 6: Polish & Documentation ✅ COMPLETE
- README.md — ✅ COMPLETE (polished with CI badges, correct repo URL, MIT license)
- Test suite — ✅ COMPLETE (158 tests across 10 files: memory/, session/, cli/, mcp/, permissions/, skills/, core/)
- CI/CD workflows — ✅ COMPLETE (.github/workflows/test.yml, lint.yml, publish.yml)
- Install scripts — ✅ COMPLETE (install.ps1, install.sh)
- Architecture documentation — ✅ Complete (docs/ARCHITECTURE.md)
- API reference — ✅ Complete (docs/API.md with REST + WebSocket + MCP endpoints)
- Contributing guide — ✅ Complete (docs/CONTRIBUTING.md)
- Security policy — ✅ Complete (docs/SECURITY.md)
- Usage examples — ✅ Complete (docs/examples/ with 4 tutorial files)

### Phase 7 & 7.5: Advanced Options & State-of-the-Art Upgrades ✅ COMPLETE
- **Fine-Tuning & Hardware Options** — ✅ COMPLETE (integrated Flash Attention, RoPE scale context stretching, unified KV cache allocation, and INT8/INT4 cache quantization inside `LocalEngine`)
- **Loading Memory Guardrails** — ✅ COMPLETE (implemented off/relaxed/balanced/strict guardrail safety checks inside `ModelManager`)
- **RAG Repository Search** — ✅ COMPLETE (implemented FTS5 SQLite codebase chunks index inside `RepositoryRAGTool`)
- **Atomic Batch Editor** — ✅ COMPLETE (implemented transactional search-replace editor with rollback inside `BatchEditTool`)
- **Hermes Goals & reasoning Budgets** — ✅ COMPLETE (mapped effort budgets to local loop iterations and remote o-series model params)
- **Rule-learning Standards** — ✅ COMPLETE (implemented dynamic workspace auto-discovery of `CLAUDE.md`, `.nexus-agent.md`, or `AGENT.md` guidelines)
- **JSONL Telemetry Tracing** — ✅ COMPLETE (implemented local tracing of agent steps, thoughts, tool latencies, and token metrics inside `.nexus-agent/traces/`)
- **Code Symbol-Aware RAG** — ✅ COMPLETE (engineered syntactic regex class and function extraction for boosted BM25-based keyword matches)

### Phase 8: Full-Spectrum Agent Capabilities ✅ COMPLETE
- **Dual-Mode Web Crawler & Scraper** — ✅ COMPLETE (built `BrowserTool` executing headless Chromium automation via Playwright, with dynamic async HTTPX HTML static extraction and Markdown conversion fallback)
- **AST-Aware Local static Linter** — ✅ COMPLETE (built `LSPClientTool` implementing offline diagnostics, compile check syntax error hooks, and regex-based symbols definition/hover queries)

### Phase 9: Full-Spectrum State-of-the-Art Architecture ✅ COMPLETE
- **Self-Healing Execution Engine** — ✅ COMPLETE (orchestrates retries with error classification and exponential backoff)
- **Reflection Critic Loops** — ✅ COMPLETE (structures code quality evaluation scoring and autonomous correction iterations)
- **Task Graph DAG Decomposer** — ✅ COMPLETE (LLM-driven recursive goal decomposition and execution sequencing)
- **Natural Language Autoencoder Telemetry** — ✅ COMPLETE (logs detailed reasoning thoughts, tools, confidence, and signals)
- **Multi-Agent Debate Consensus** — ✅ COMPLETE (runs security, performance, correctness, and style reviews in parallel)
- **DevOps local CI Pipeline** — ✅ COMPLETE (automatic framework detection, linter audits, secrets scanning, and traceback analysis)
- **Smart Git conventional commits** — ✅ COMPLETE (auto-diff-based commit message and PR overview details)
- **AST Python Call Graph tools** — ✅ COMPLETE (caller-callee resolution, module import adjacency maps, and scope symbol renamer)
- **FastAPI API & terminal TUI integrations** — ✅ COMPLETE (gated websocket controllers, status updates, and interactive commands)


---

## 5. DEPENDENCY MAP

### Core Dependencies (in `pyproject.toml`)
| Package | Purpose | Why This One |
|:---|:---|:---|
| `llama-cpp-python>=0.3.0` | Local GGUF model loading & inference | Only Python binding to llama.cpp with full tool calling support |
| `click>=8.1.0` | CLI argument parsing | Industry standard, integrates with Rich |
| `rich>=13.0.0` | Terminal formatting (tables, panels, syntax highlighting) | Required by Textual, best terminal renderer |
| `textual>=0.80.0` | Full-screen TUI framework | Best Python TUI framework, CSS-like styling |
| `fastapi>=0.115.0` | GUI web server | Async, WebSocket native, high performance |
| `uvicorn[standard]>=0.30.0` | ASGI server for FastAPI | Standard FastAPI runner |
| `websockets>=12.0` | WebSocket support | Real-time LLM streaming to GUI |
| `pyyaml>=6.0` | YAML config parsing | For `config/default.yaml` and user configs |
| `aiosqlite>=0.20.0` | Async SQLite for memory/sessions | Non-blocking DB access in async contexts |
| `httpx>=0.27.0` | HTTP client for web search & API calls | Modern async-capable HTTP client |
| `pydantic>=2.0.0` | Data validation | API request/response schemas |
| `psutil>=5.9.0` | Hardware detection (RAM, CPU) | For `model_manager.detect_hardware()` |
| `platformdirs>=4.0.0` | OS-appropriate data directories | Cross-platform config/data paths |
| `pygments>=2.18.0` | Syntax highlighting | For code display in TUI and GUI |

### Optional Dependencies
| Group | Packages | Purpose |
|:---|:---|:---|
| `[gpu]` | `llama-cpp-python[cuda]` | CUDA GPU acceleration |
| `[providers]` | `openai`, `anthropic`, `google-generativeai`, `boto3` | Cloud provider SDKs |
| `[mcp]` | `mcp>=1.0.0` | Model Context Protocol support |
| `[dev]` | `pytest`, `ruff`, `mypy` | Development tools |

---

## 6. CONTINUATION PROMPT FOR OTHER LLM AGENTS

Use the following prompt to continue development of this project:

---

**CONTINUATION PROMPT:**

```
You are continuing development of NexusAgent, an offline-first LLM coding agent located at D:/Project/nexus-agent/.

READ THESE FILES FIRST:
1. D:/Project/nexus-agent/docs/CONTEXT.md — Full project context, architecture, status
2. D:/Project/nexus-agent/docs/MEMORY.md — Detailed implementation memory log

PROJECT STATE: Phase 2 is ~70% complete. The remaining Phase 2 items are:
- permissions/manager.py and permissions/rules.py
- session/manager.py, session/storage.py, session/checkpoint.py

After Phase 2, continue with:
- Phase 3: CLI TUI interface (Textual-based, files in src/nexus_agent/cli/)
- Phase 4: GUI web interface (FastAPI + HTML/CSS/JS, files in src/nexus_agent/gui/)
- Phase 5: Advanced features (orchestrator, planner, executor, skills, MCP, cloud providers)
- Phase 6: Polish, README, tests, docs

KEY RULES:
1. The project uses Python 3.10+, no TypeScript/Go/Rust
2. Local LLM hosting via llama-cpp-python is the DEFAULT and PRIMARY mode
3. All LLM providers implement the LLMProvider interface in llm/base.py
4. The agent loop is in core/agent.py — do not restructure it
5. Memory uses SQLite FTS5 — do not add vector databases
6. CLI uses Textual framework, GUI uses FastAPI + vanilla HTML/CSS/JS
7. Follow the existing code patterns in implemented files
8. Update docs/MEMORY.md after every significant implementation step
9. Update docs/CONTEXT.md section 2.2 (directory status) and section 4 (phase status) as you work

CURRENT pyproject.toml entry point: nexus = "nexus_agent.__main__:main"
```

---
