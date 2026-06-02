# NexusAgent — Exhaustive Project Report

> **Generated:** 2026-06-02
> **Version:** 0.1.0 (Alpha)
> **Status:** Phase A-E Complete — Claimed Production-ready v1.0 (~60% truly production-ready per internal audit)
> **License:** MIT

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What the Project Is](#2-what-the-project-is)
3. [Design Philosophy & Differentiators](#3-design-philosophy--differentiators)
4. [Inspiration Sources](#4-inspiration-sources)
5. [Tech Stack](#5-tech-stack)
6. [Project Structure](#6-project-structure)
7. [Implemented Features — Complete Catalog](#7-implemented-features--complete-catalog)
8. [Planned / Partially Implemented Features](#8-planned--partially-implemented-features)
9. [Architecture Deep Dive](#9-architecture-deep-dive)
10. [Security Model](#10-security-model)
11. [Test Coverage](#11-test-coverage)
12. [Hardware Acceleration Matrix](#12-hardware-acceleration-matrix)
13. [Known Issues & Gaps (from FRESH_AUDIT.md)](#13-known-issues--gaps-from-freshauditmd)
14. [Documentation Map](#14-documentation-map)
15. [Project Metadata](#15-project-metadata)

---

## 1. Executive Summary

**NexusAgent** is a premium, **offline-first AI coding agent** that runs entirely on the user's local machine. Its core differentiator from all other coding agents (claude-code, opencode, codex, letta, etc.) is that it **loads and runs GGUF LLM models directly on-device** via `llama-cpp-python` and `onnxruntime-genai`, requiring zero internet connectivity by default. Cloud providers are supported as optional add-ons.

The project aggregates the best architectural ideas from 8 reference projects into a single unified system with both a **Textual-based terminal TUI** and a **FastAPI-based web GUI**. It features a database-backed 4-tier memory system, a 13-tool extensible tool system, modular markdown-based skills, MCP protocol support, a permission-gated security model, multi-agent orchestration, and a local CI/devops pipeline.

**Current codebase:** 91 Python source files (~25,000+ lines), 11 test files (~158 tests), 20+ documentation files.

---

## 2. What the Project Is

NexusAgent is a **local-first AI coding assistant** that helps developers write, debug, refactor, and understand code through an interactive agentic loop. It can be used in two interface modes:

- **CLI (Textual TUI):** Full-screen terminal dashboard with interactive workspace file tree, syntax-highlighted diff viewer, permission approval overlays, multi-panel chat layout, dark/light theme support, and slash commands.
- **GUI (FastAPI Web):** Responsive 3-column glassmorphic dark-theme dashboard served from a local web server (no Electron/Chrome bundle), with real-time WebSocket streaming of LLM responses.

The agent can operate in 4 modes:
1. **AUTO:** Fully autonomous, executes tools and generates responses without user confirmation on safe operations.
2. **PLAN:** Read-only planning sub-agent — researches and formulates a plan without modifying files.
3. **BUILD:** Write-capable execution sub-agent — implements plans by editing files and running commands.
4. **REVIEW:** Code review sub-agent — analyzes diffs and provides structured feedback.

---

## 3. Design Philosophy & Differentiators

| Principle | Description |
|-----------|-------------|
| **Offline-First** | Local GGUF model hosting is the default. Cloud providers are optional add-ons. Privacy-preserving by design. |
| **Provider-Agnostic** | Unified `LLMProvider` interface — swap between local/cloud with one config change. |
| **Agentic Loop** | Gather → Act → Verify cycle with streaming and permission callbacks. |
| **Persistent Memory** | Agent remembers across sessions via 4-tier memory (inspired by MemGPT/letta and hermes). |
| **Dual Interface** | Rich terminal TUI (Textual) + web-based GUI (FastAPI) sharing the same core. |
| **Permission-Gated Tools** | Every tool action goes through permission checks (allow/ask/deny) with 3 modes: suggest, ask, auto. |
| **Modular Skills** | Markdown-based skill files (SKILL.md) with YAML frontmatter that register as tools and spawn sub-agents. |
| **Multi-Agent Architecture** | Planner → Executor → Reviewer loop with orchestration, debate consensus, and task decomposition. |
| **Self-Healing** | Error classification, exponential backoff retry, and reflection loops for autonomous correction. |
| **Zero External Dependencies** | SQLite FTS5 for memory (no vector DB), local web server (no Electron), DuckDuckGo for search (no API key). |

### What Makes It Unique

**No existing agent loads LLM models locally on the machine where the agent itself runs.** All current agents (claude-code, opencode, codex, etc.) connect to cloud APIs. NexusAgent uses `llama-cpp-python` and `onnxruntime-genai` to load GGUF and ONNX models directly into RAM/VRAM/NPU for local execution.

---

## 4. Inspiration Sources

| Source Project | What Was Adopted | Where It Lives |
|----------------|------------------|----------------|
| **claude-code** | Agentic loop (gather→act→verify), checkpoint/rollback, streaming, CLAUDE.md config | `core/agent.py`, `session/checkpoint.py` |
| **opencode** | Provider abstraction, Plan/Build modes, TUI layout, auto-compact, LSP integration, permission model | `llm/base.py`, `llm/providers/`, `core/planner.py`, `core/executor.py`, `permissions/` |
| **openclaw** | Skill system via Markdown SKILL.md files, web control UI | `skills/`, built-in skill `.md` files |
| **letta (MemGPT)** | Persistent stateful memory, working/long-term/episodic architecture | `memory/` (all files) |
| **jules** | Multi-agent orchestration (planner→executor→tester→reviewer) | `core/orchestrator.py` |
| **antigravity-cli** | Sub-agent spawning, shared core between CLI/GUI | `core/orchestrator.py`, shared `cli/`/`gui/` core |
| **hermes agent** | FTS5 memory over SQLite, user preference profiles, self-improvement | `memory/user_profile.py`, `memory/long_term.py` |
| **codex (OpenAI)** | Sandboxed execution, approval modes (suggest/ask/auto) | `core/sandbox.py` |

---

## 5. Tech Stack

### Primary Language
- **Python 3.10+** (strict type annotations via `mypy --strict`)

### Core Framework & CLI

| Component | Technology | Purpose |
|-----------|------------|---------|
| TUI (Terminal) | **Textual** (Python TUI framework, CSS-like `.tcss` styling) | Interactive terminal dashboard |
| CLI Framework | **Click** (8.1+) | Command-line argument parsing |
| Terminal Rendering | **Rich** (13.0+) | Tables, panels, markdown, syntax highlighting |

### GUI (Web)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Server | **FastAPI** (0.115+) | Async REST + WebSocket server |
| ASGI Runner | **Uvicorn** (0.30+) | ASGI server |
| Frontend | **Vanilla HTML/CSS/JS** | Responsive glassmorphic dark-theme dashboard |
| Real-time | **WebSockets** (12.0+) | Live streaming of LLM responses |

### LLM & ML

| Component | Technology | Purpose |
|-----------|------------|---------|
| Local Inference | **`llama-cpp-python`** (0.3+) | GGUF model loading, GPU offloading, tool calling |
| NPU Inference | **`onnxruntime-genai`** + **`onnxruntime-directml`** | Windows NPU (Qualcomm, Intel) |
| Cloud Providers | OpenAI, Anthropic, Google, Groq, DeepSeek, OpenRouter, AWS Bedrock, Ollama, Custom | 9 cloud backends via native `httpx` |

### Memory & Storage

| Component | Technology | Purpose |
|-----------|------------|---------|
| Long-term Memory | **aiosqlite** with **FTS5** full-text search | Persistent cross-session recall |
| Episodic Memory | **aiosqlite** with **FTS5** | Session history search |
| User Profile | **YAML** files | Learned user preferences |
| Configuration | **PyYAML** (6.0+) | Multi-layer config (default → user → project → env → CLI) |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `pydantic` (2.0+) | Data validation, API schemas |
| `httpx` (0.27+) | Async HTTP client for cloud providers & web search |
| `psutil` (5.9+) | Hardware detection (CPU, RAM) |
| `platformdirs` (4.0+) | OS-appropriate data directories |
| `pygments` (2.18+) | Syntax highlighting |
| `tree-sitter` (0.22+) | Code parsing |
| `jinja2` (3.1+) | Template rendering |
| `watchfiles` (0.21+) | File watching |
| `python-dotenv` (1.0+) | `.env` file loading |

### Development

| Tool | Purpose |
|------|---------|
| `ruff` | Linting (line length 100, target py310) |
| `mypy` | Strict static type checking |
| `pytest` (with `pytest-asyncio`) | Testing framework |
| `pytest-cov` | Coverage reporting |

---

## 6. Project Structure

```
D:\Project\nexus-agent/
├── pyproject.toml                    # Project metadata, dependencies, build config
├── .env.example                      # Environment variables template
├── .gitignore
├── README.md                         # Main user-facing documentation
├── REQUIREMENTS.md
├── memory.md                         # Agent memory notes
├── AUDIT_REPORT.md
├── PROJECT_REPORT.md                 # This file
│
├── install.ps1                       # Windows PowerShell installer (Astral uv)
├── install.sh                        # Linux/macOS bash installer (Astral uv)
│
├── config/
│   └── default.yaml                  # Full default YAML configuration (378 lines)
│
├── .github/workflows/
│   ├── test.yml                      # CI: run tests on push
│   ├── lint.yml                      # CI: run ruff + mypy on push
│   └── publish.yml                   # CD: publish to PyPI on tag
│
├── src/nexus_agent/                  # Main Python package (91 .py files)
│   ├── __init__.py                   # Version 0.1.0
│   ├── __main__.py                   # CLI entry: chat, gui, model, session, config, hardware, wizard, browse, plan, devops
│   ├── _default_config.yaml          # Bundled default config
│   │
│   ├── core/                         # Core reasoning engine
│   │   ├── agent.py                  # AgentLoop: gather->act->verify cycle (642 lines)
│   │   ├── config.py                 # Multi-layer config loader
│   │   ├── context.py                # Auto-compaction context manager
│   │   ├── sandbox.py                # Sandboxed command execution (368 lines)
│   │   ├── orchestrator.py           # Multi-agent coordinator (313 lines)
│   │   ├── planner.py                # Read-only planning sub-agent
│   │   ├── executor.py               # Write-capable execution sub-agent
│   │   ├── task_graph.py             # Hierarchical task DAG (348 lines)
│   │   ├── nla_telemetry.py          # Reasoning telemetry logging
│   │   ├── debate.py                 # Multi-agent debate consensus (336 lines)
│   │   ├── devops.py                 # Local CI pipeline (392 lines)
│   │   ├── reflection.py             # Generator-critic reflection loop (361 lines)
│   │   ├── self_heal.py              # Self-healing execution engine (345 lines)
│   │   └── sqlite_store.py           # General-purpose SQLite helper
│   │
│   ├── llm/                          # LLM provider layer
│   │   ├── base.py                   # Abstract LLMProvider interface, Message, ToolCall, etc.
│   │   ├── local_engine.py           # llama-cpp-python GGUF engine (large file)
│   │   ├── model_manager.py          # GGUF discovery, hardware detection, guardrails (421 lines)
│   │   ├── onnx_engine.py            # ONNX Runtime (stub/placeholder)
│   │   ├── runtime_manager.py        # Runtime selection (llama.cpp, ONNX, Ollama)
│   │   └── providers/                # 9 cloud provider implementations
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       ├── google_provider.py
│   │       ├── groq_provider.py
│   │       ├── deepseek_provider.py
│   │       ├── openrouter_provider.py
│   │       ├── ollama_provider.py
│   │       ├── aws_bedrock_provider.py
│   │       ├── custom_openai_provider.py
│   │       └── factory.py
│   │
│   ├── memory/                       # Stateful memory system
│   │   ├── memory_manager.py         # Orchestrates all memory subsystems
│   │   ├── working_memory.py         # In-memory LRU scratchpad
│   │   ├── long_term.py              # SQLite FTS5 persistent recall
│   │   ├── episodic.py               # Session history with FTS5
│   │   └── user_profile.py           # YAML-backed preference learning
│   │
│   ├── tools/                        # Tool implementations (13 files)
│   │   ├── base.py                   # Abstract Tool class
│   │   ├── file_ops.py               # Read, Write, Search, ListDirectory (426 lines)
│   │   ├── shell.py                  # Sandboxed shell execution
│   │   ├── code_edit.py              # Search-replace + insert with diff
│   │   ├── git_ops.py                # Git operations + SmartCommit (316 lines)
│   │   ├── web_search.py             # DuckDuckGo search
│   │   ├── lsp_client.py             # LSP diagnostics / AST linter
│   │   ├── browser.py                # Playwright + HTTPX browser
│   │   ├── rag_search.py             # FTS5 code search with symbol extraction
│   │   ├── batch_edit.py             # Transactional batch editor
│   │   └── code_intel.py             # AST code intelligence (317 lines)
│   │
│   ├── skills/                       # Modular skill system
│   │   ├── skill_loader.py           # Markdown .md skill parser
│   │   ├── skill_registry.py         # Skill registry + tool exposure
│   │   └── builtin/                  # 5 built-in skill definitions (.md files)
│   │       ├── code_review.md
│   │       ├── debug.md
│   │       ├── documentation.md
│   │       ├── refactor.md
│   │       └── test_writer.md
│   │
│   ├── mcp/                          # Model Context Protocol
│   │   ├── client.py                 # MCP stdio client
│   │   ├── server.py                 # MCP stdio server
│   │   └── transport.py              # JSON-RPC 2.0 stdio transport
│   │
│   ├── session/                      # Session management
│   │   ├── manager.py                # Session lifecycle
│   │   ├── storage.py                # SQLite session storage
│   │   └── checkpoint.py             # Git worktree checkpoint/rollback
│   │
│   ├── permissions/                  # Security permission system
│   │   ├── manager.py                # Permission evaluation engine
│   │   └── rules.py                  # Permission rule definitions
│   │
│   ├── cli/                          # Textual TUI implementation (13 files)
│   │   ├── app.py                    # Main TUI application
│   │   ├── command_dispatcher.py     # Slash command routing (2021 lines — largest file)
│   │   ├── renderer.py               # Terminal rendering (1422 lines)
│   │   ├── input_handler.py          # Input processing (753 lines)
│   │   ├── wizard.py                 # First-run setup wizard
│   │   ├── auth.py                   # API key management
│   │   ├── theme.py                  # Dark/light theme
│   │   ├── file_tree.py              # Directory tree sidebar
│   │   ├── diff_view.py              # Syntax-highlighted diff viewer
│   │   ├── approval_dialog.py        # Permission overlay
│   │   ├── models_db.py              # Model database/cache
│   │   ├── runtimes.py               # Runtime detection
│   │   ├── session_handler.py        # Session integration (312 lines)
│   │   ├── event_handler.py          # Textual event handling
│   │   └── styles.tcss               # Textual CSS styles
│   │
│   ├── gui/                          # FastAPI web GUI implementation
│   │   ├── server.py                 # FastAPI server (565 lines)
│   │   ├── api/                      # Empty directory (to be split from server.py)
│   │   └── frontend/                 # Static web frontend
│   │       ├── index.html            # 3-column glassmorphic dashboard
│   │       ├── css/styles.css        # Dark theme stylesheet
│   │       └── js/                   # 5 JS modules
│   │           ├── app.js            # Master orchestrator
│   │           ├── chat.js           # WebSocket streaming chat
│   │           ├── models.js         # Model management
│   │           ├── settings.js       # User preferences
│   │           └── utils.js          # Helpers
│   │
│   ├── protocol/
│   │   └── agent_protocol.py         # XML/JSON agent protocol (716 lines)
│   │
│   └── training/                     # Early-stage training module
│       ├── colab/
│       ├── data/
│       ├── interpretability/
│       ├── model/
│       └── server/
│
├── tests/                            # Test suite (11 test files, ~158 tests)
│   ├── test_imports.py               # Package import verification
│   ├── test_providers.py             # Cloud provider tests
│   ├── test_advanced.py              # Advanced feature tests (437 lines)
│   └── nexus_agent/                  # Mirrors source structure
│       ├── cli/
│       │   ├── test_cli.py
│       │   └── test_wizard.py
│       ├── core/test_core.py
│       ├── mcp/test_mcp.py
│       ├── memory/test_memory.py
│       ├── permissions/test_permissions.py
│       ├── session/test_session.py
│       └── skills/test_skills.py
│
└── docs/                             # Documentation (20+ files)
    ├── CONTEXT.md                    # Main project context/continuation guide
    ├── MEMORY.md                     # Chronological implementation memory log (516 lines)
    ├── ARCHITECTURE.md               # System architecture & data flow (278 lines)
    ├── API.md                        # REST + WebSocket + MCP API reference (379 lines)
    ├── ROADMAP.md                    # Detailed execution roadmap (197 lines)
    ├── FRESH_AUDIT.md                # Code quality audit report (773 lines)
    ├── SECURITY.md                   # Security model (140 lines)
    ├── CONTRIBUTING.md               # Contribution guidelines (260 lines)
    ├── CUSTOM_INFERENCE_SERVER.md
    ├── task.md
    ├── implementation_plan.md
    ├── Offline Localized AI Agent.md
    └── examples/
        ├── getting_started.md
        ├── local_models.md
        ├── cloud_providers.md
        └── cli_reference.md
```

---

## 7. Implemented Features — Complete Catalog

### 7.1 Core Agent System
- **Agentic Loop** (`core/agent.py`): Gather → Act → Verify cycle with 4 modes (AUTO, PLAN, BUILD, REVIEW)
- **Streaming Responses**: Generator pattern for real-time UI updates
- **Tool Calling**: JSON Schema-based tool definitions (OpenAI-compatible format)
- **Context Window Management**: Auto-compaction at 85% threshold with tool output trimming
- **Self-Healing Execution Engine** (`core/self_heal.py`): Error classification, exponential backoff, retry with configurable max attempts
- **Generator-Critic Reflection Loops** (`core/reflection.py`): Scores agent responses 0-100, triggers autonomous self-correction
- **Sub-Agent Delegation**: Orchestrator → Planner → Executor pipeline

### 7.2 LLM Provider System
- **Unified `LLMProvider` abstract interface** (`llm/base.py`) with `Message`, `ToolCall`, `ToolDefinition`, `LLMResponse`, `StreamChunk`, `ProviderCapabilities`
- **Local Engine** (`llm/local_engine.py`): GGUF model loading via `llama-cpp-python` with:
  - GPU auto-detection (CUDA, Vulkan, Metal, ROCm, SYCL, OpenVINO)
  - Chat format auto-detection (LLaMA, Mistral, ChatML, etc.)
  - Streaming text generation
  - Tool calling (grammar-based for local models)
  - Model hot-swapping
  - Flash Attention support
  - KV Cache Quantization (INT8/INT4)
  - RoPE scale context stretching
  - Unified KV cache allocation
- **Model Manager** (`llm/model_manager.py`): GGUF file discovery, metadata extraction from filename, hardware detection, model recommendation, memory guardrails (4 levels)
- **Runtime Manager** (`llm/runtime_manager.py`): Auto-detection and selection between llama.cpp, ONNX, and Ollama runtimes
- **9 Cloud Providers**: OpenAI, Anthropic, Google/Gemini, Groq, DeepSeek, OpenRouter, AWS Bedrock, Ollama, Custom OpenAI-compatible
- **ONNX Engine** (`llm/onnx_engine.py`): Stub/placeholder (raises `NotImplementedError`)

### 7.3 Memory System (4-Tier)
- **Working Memory** (`memory/working_memory.py`): In-memory LRU scratchpad using `OrderedDict` (default 100 entries)
- **Long-term Memory** (`memory/long_term.py`): SQLite FTS5 full-text search across sessions with automatic summarization
- **Episodic Memory** (`memory/episodic.py`): SQLite FTS5 session history with chronological search
- **User Profile** (`memory/user_profile.py`): YAML-backed preference learning (coding style, communication preferences, behavior patterns)
- **Cross-Memory Search**: Combined search across all 4 tiers with context injection into prompts

### 7.4 Tool System (13 Tools)
| Tool | File | Capabilities |
|------|------|-------------|
| ReadFileTool | `tools/file_ops.py` | Read files with offset/limit, text/binary detection |
| WriteFileTool | `tools/file_ops.py` | Write content to files |
| SearchFilesTool | `tools/file_ops.py` | Regex pattern search across files |
| ListDirectoryTool | `tools/file_ops.py` | Directory listing with file info |
| ShellTool | `tools/shell.py` | Sandboxed command execution with risk classification |
| CodeEditTool | `tools/code_edit.py` | Search-replace with unified diff output |
| InsertLinesTool | `tools/code_edit.py` | Line insertion at specified positions |
| GitTool | `tools/git_ops.py` | Git operations with safety checks (blocks push, force-push, reset --hard, clean -fdx) + SmartCommit (conventional commit generation, PR creation, CI log analysis) |
| WebSearchTool | `tools/web_search.py` | DuckDuckGo search (no API key needed) |
| LSPClientTool | `tools/lsp_client.py` | AST-based Python linter (diagnostics, compile checks, symbol queries) |
| BrowserTool | `tools/browser.py` | Playwright headless browser + HTTPX fallback with HTML-to-Markdown conversion |
| RepositoryRAGTool | `tools/rag_search.py` | FTS5 codebase chunk indexing with symbol extraction (classes, functions) |
| BatchEditTool | `tools/batch_edit.py` | Transactional multi-file search-replace with rollback on failure |
| CodeIntelTool | `tools/code_intel.py` | AST call graphs, module import maps, scope-safe symbol renaming |

### 7.5 Permission System
- **3 Permission Modes**: SUGGEST (display only), ASK (prompt user), AUTO (rule-based)
- **Risk Levels**: SAFE, MODERATE, DANGEROUS, BLOCKED
- **Regex-based patterns**: Allowed/denied command patterns
- **Permission Evaluation**: Callback in agent loop gates tool execution
- **GUI Approval Dialog**: Modal overlay for user approval in TUI

### 7.6 Session & Checkpoint System
- **Session Lifecycle**: Create, resume, list, delete sessions
- **SQLite-backed Storage**: Message history with pagination
- **Checkpoint/Rollback**: Git worktree snapshots (inspired by claude-code's `/rewind`)
- **Auto-save**: Configurable interval-based persistence

### 7.7 Skill System
- **Markdown `.md` Skill Files**: YAML frontmatter metadata (name, description, tools, model)
- **SkillLoader**: Parses markdown frontmatter and extracts instructions
- **SkillRegistry**: Maps skills to tool definitions
- **5 Built-in Skills**:
  - `code_review.md` — Reviews code diffs for quality, security, performance
  - `debug.md` — Interactive debugging workflow
  - `documentation.md` — Generates docstrings and documentation
  - `refactor.md` — Code refactoring with safety checks
  - `test_writer.md` — Automated test generation

### 7.8 MCP (Model Context Protocol)
- **JSON-RPC 2.0 Stdio Transport**
- **MCP Client**: Connects to external MCP servers for dynamic tool discovery
- **MCP Server**: Exposes NexusAgent tools as MCP endpoints
- **Dynamic Tool Discovery**: Tools are registered/unregistered at runtime

### 7.9 CLI (Textual TUI) — 13 Files
- **NexusApp** (`cli/app.py`): Main Textual application with multi-panel layout
- **CommandDispatcher** (`cli/command_dispatcher.py`): Slash command routing (2021 lines) — `/reflect`, `/task`, `/debate`, `/verify`, `/nla`, `/commit`
- **Renderer** (`cli/renderer.py`): Rich-based terminal rendering (1422 lines) — Markdown, syntax highlighting, tables, panels
- **InputHandler** (`cli/input_handler.py`): Input processing (753 lines) — multi-line input, history, completion
- **Wizard** (`cli/wizard.py`): Interactive first-run setup wizard with hardware detection, model recommendation, config generation
- **Auth** (`cli/auth.py`): API key management (encrypted storage via `cryptography`)
- **Theme** (`cli/theme.py`): Dark/light theme with custom color schemes
- **FileTree** (`cli/file_tree.py`): Interactive directory tree sidebar with git status indicators
- **DiffView** (`cli/diff_view.py`): Syntax-highlighted unified diff viewer
- **ApprovalDialog** (`cli/approval_dialog.py`): ModalScreen permission approval overlay
- **ModelsDB** (`cli/models_db.py`): Model database and cache
- **Runtimes** (`cli/runtimes.py`): Runtime detection and management
- **SessionHandler** (`cli/session_handler.py`): Session integration (312 lines)
- **EventHandler** (`cli/event_handler.py`): Textual event handling
- **Styles** (`cli/styles.tcss`): Textual CSS styles for layout and theming

### 7.10 GUI (FastAPI Web) — 8 Files
- **Server** (`gui/server.py`): FastAPI server with REST + WebSocket endpoints (565 lines)
  - `GET /api/status` — Server status
  - `GET /api/models` — List available models
  - `POST /api/models/load` — Load a model
  - `POST /api/models/unload` — Unload current model
  - `GET /api/sessions` — List sessions
  - `POST /api/sessions` — Create session
  - `POST /api/sessions/{id}/resume` — Resume session
  - `POST /api/chat` — Send chat message
  - `WS /api/ws` — WebSocket chat with streaming
  - `WS /api/ws/models` — WebSocket model monitoring
  - `GET /api/nla/telemetry` — NLA telemetry data
- **Frontend HTML** (`gui/frontend/index.html`): 3-column glassmorphic dashboard with:
  - Left panel: Model info, system status
  - Center panel: Chat interface with streaming
  - Right panel: Sessions, settings, NLA telemetry
- **Frontend CSS** (`gui/frontend/css/styles.css`): Dark theme with glassmorphism, glow effects, transitions
- **Frontend JS** (5 modules):
  - `app.js` — Master orchestrator, WebSocket management
  - `chat.js` — Chat UI, message rendering, streaming
  - `models.js` — Model list, load/unload controls
  - `settings.js` — User preferences (localStorage)
  - `utils.js` — Helpers, date formatting, Markdown parsing

### 7.11 Advanced Architecture Features
- **Task Graph DAG** (`core/task_graph.py`): LLM-driven recursive goal decomposition (max depth 3), Mermaid chart visualization, persistence to JSON
- **NLA Telemetry** (`core/nla_telemetry.py`): Reasoning step logging (thoughts, tools, confidence, alternatives) to JSONL trace files in `~/.nexus-agent/traces/`
- **Multi-Agent Debate** (`core/debate.py`): 4 parallel reviewer personas (Security, Performance, Correctness, Style) with Judge aggregation and consensus scoring
- **DevOps CI Pipeline** (`core/devops.py`): Test framework auto-detection (pytest, cargo, jest, go), linter integration, secrets scanning, traceback analysis
- **Workspace Rule Discovery**: Auto-detects `CLAUDE.md`, `.nexus-agent.md`, `AGENT.md` guidelines
- **Memory Guardrails**: 4 levels (off/relaxed/balanced/strict) for model loading safety checks
- **Flash Attention & KV Cache Quantization**: Performance optimizations in `LocalEngine`
- **Effort Budgets**: Maps reasoning effort to loop iterations and model parameters
- **Smart Git**: Conventional commit generation, PR markdown creator, CI log diagnostics

### 7.12 Configuration System
- **6-Layer Config** (highest priority last):
  1. Default config (`nexus_agent/_default_config.yaml`)
  2. User config (`~/.nexus-agent/config.yaml`)
  3. Project config (`./.nexus-agent.yaml`)
  4. Environment variables (`NEXUS_*` prefix)
  5. CLI `--config` flag
  6. CLI `--model`, `--provider` flags
- **Full YAML Config**: Covers agent mode, local model settings, hardware backends, all 9 cloud providers, memory settings, session settings, permissions, skills, MCP, GUI, CLI
- **Environment Variable Overrides**: `NEXUS_PROVIDER`, `NEXUS_MODEL`, `NEXUS_MODE`, etc.

### 7.13 Installation & Distribution
- **Windows PowerShell Installer** (`install.ps1`): Uses Astral `uv` for fast dependency resolution
- **Linux/macOS Bash Installer** (`install.sh`): Uses Astral `uv`
- **PyPI Publishing**: Automated via `publish.yml` GitHub workflow
- **Optional Dependency Groups**: `[cuda]`, `[vulkan]`, `[rocm]`, `[metal]`, `[sycl]`, `[npu]`, `[openvino]`, `[tpu]`, `[gui]`, `[providers]`, `[mcp]`, `[all]`

### 7.14 Training Module (Early Stage)
- Located in `src/nexus_agent/training/`
- Subdirectories for: `colab/`, `data/`, `interpretability/`, `model/`, `server/`
- Very early stage — mostly scaffolding

---

## 8. Planned / Partially Implemented Features

### From ROADMAP.md and FRESH_AUDIT.md

| Feature | Status | Priority | Notes |
|---------|--------|----------|-------|
| **ONNX Engine Completion** | Partial (stub) | P0 | `onnx_engine.py` raises `NotImplementedError`. No actual NPU inference. |
| **Shell Command Injection Fix** | Known issue | P0 | `sandbox.py` has potential shell injection via `shell=True` edge case |
| **`local_engine.py` Refactor** | Not started | P1 | 839-line file needs splitting into focused modules |
| **`agent.py` `run()` Refactor** | Not started | P1 | 150+ line method needs breaking down |
| **Docker Sandbox Fallback** | Not started | P1 | Currently assumes Docker is installed with no graceful fallback |
| **Comprehensive Test Coverage** | Partial | P1 | ~158 tests, many modules lack coverage (>80% gap) |
| **Provider Latency Tracking** | Not started | P2 | Smart Router for task-based provider selection |
| **Linux Port Verification** | Not started | P2 | Primarily developed on Windows |
| **PWA for GUI** | Not started | P3 | Progressive Web App support |
| **iOS Safari GUI** | Not started | P3 | Mobile browser access |
| **Native iOS App** | Not started | P3 | Tauri-based native app |
| **Tauri Desktop Apps** | Not started | P3 | Native desktop bundles for Windows/macOS/Linux |
| **Python Plugin System** | Not started | P3 | User-extensible plugin architecture |
| **Multi-User / Cloud Sync** | Not started | P3 | Shared memory/sessions across instances |
| **Phase 9 Gaps** | Various | P0-P3 | Some components documented as missing but later re-implemented; audit needed |

---

## 9. Architecture Deep Dive

### 9.1 Agent Loop (Core)

The `AgentLoop` in `core/agent.py` implements a synchronous gather→act→verify cycle:

```
while iterations < max_iterations:
    1. GATHER: LLM generates tool_calls or text response
    2. ACT: Execute approved tool calls (permission callback gates)
    3. VERIFY: Check tool outputs, retry on failure
    4. STREAM: Send events to UI via callback
```

Key attributes:
- `AgentMode`: `auto`, `plan`, `build`, `review`
- `AgentEvent`: `thinking`, `content_chunk`, `tool_call`, `tool_result`, `error`, `done`
- Supports streaming via generator pattern
- Customizable max iterations, temperature, top_p

### 9.2 Data Flow

```
User Input
    │
    ▼
┌──────────────┐
│  AgentLoop   │
│  (agent.py)  │
└──┬───────┬───┘
   │       │
   ▼       ▼
┌────────┐ ┌──────────┐
│Memory  │ │  LLM     │
│Manager │ │ Provider │
└────────┘ └────┬─────┘
                │
        ┌───────┼───────────┐
        │       │           │
   ┌────▼──┐ ┌──▼───┐ ┌───▼────┐
   │Local  │ │Cloud │ │ Ollama │
   │Engine │ │ APIs │ │ Server │
   └───────┘ └──────┘ └────────┘
```

### 9.3 Memory Architecture

```
┌─────────────────────────────────────┐
│          MemoryManager              │
│  (orchestrates all subsystems)      │
└───┬────────┬────────┬───────────────┘
    │        │        │
    ▼        ▼        ▼
┌────────┐┌────────┐ ┌──────────┐┌────────────┐
│Working ││Long    │ │Episodic  ││User Profile│
│Memory  ││Term    │ │Memory    ││(YAML)      │
│(LRU)   ││(FTS5)  │ │(FTS5)   ││            │
└────────┘└────────┘ └──────────┘└────────────┘
```

Key operations:
- `get_context_for_prompt(query)` — Merges relevant context from all tiers into a prompt prefix
- `search_cross_memory(query)` — Queries across all tiers simultaneously
- `save_session_summary()` — Called on session end to persist summaries into long-term memory

### 9.4 Permission System

```
┌──────────────────────────────────────────┐
│          PermissionManager               │
│  evaluates: tool + command + risk level  │
└───┬────────────┬──────────────┬──────────┘
    │            │              │
    ▼            ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────────┐
│SUGGEST │ │   ASK    │ │    AUTO      │
│(display│ │(prompt   │ │ (rule-based  │
│ only)  │ │ user)    │ │  decision)   │
└────────┘ └──────────┘ └──────────────┘
```

### 9.5 Config Layering

```
Priority (HIGH → LOW):
1. CLI --model, --provider, --config flags
2. Environment variables (NEXUS_*)
3. Project config (.nexus-agent.yaml)
4. User config (~/.nexus-agent/config.yaml)
5. Default config (_default_config.yaml)
```

---

## 10. Security Model

### Sandbox
- All shell commands go through `Sandbox` class
- Uses `shlex.split()` + `subprocess.run(shell=False)` — no shell interpretation of arguments
- Regex-based `dangerous_indicators` pattern detection (rm -rf, dd, mkfs, etc.)
- Risk classification: SAFE, MODERATE, DANGEROUS, BLOCKED

### Authentication
- API keys stored in `~/.nexus-agent/auth.json` (file permissions 600)
- Keys are never logged or exposed in error messages
- Environment variable fallback (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)

### Network Security
- FastAPI server binds to `127.0.0.1` only by default
- CORS restricted to localhost origins
- Rate limiting: 100 requests per minute
- Request body size limit: 10 MB
- CSP headers set on all responses
- `X-Frame-Options: DENY` to prevent clickjacking

### Git Safety
- Worktree isolation for checkpoint/rollback
- Blocks dangerous operations: push, force-push, reset --hard, clean -fdx
- All git operations go through `GitTool` safety wrapper

---

## 11. Test Coverage

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `tests/test_imports.py` | ~5 | Package import verification |
| `tests/test_advanced.py` | ~20 | Advanced features (437 lines) |
| `tests/test_providers.py` | ~20 | Cloud provider API compatibility |
| `tests/nexus_agent/cli/test_cli.py` | 14 | CLI components |
| `tests/nexus_agent/cli/test_wizard.py` | 3 | Setup wizard |
| `tests/nexus_agent/core/test_core.py` | 8 | Config, sqlite_store |
| `tests/nexus_agent/memory/test_memory.py` | 35 | All 4 memory subsystems |
| `tests/nexus_agent/session/test_session.py` | 17 | Session and checkpoint |
| `tests/nexus_agent/permissions/test_permissions.py` | 18 | Permission evaluation |
| `tests/nexus_agent/skills/test_skills.py` | 7 | Skill registry |
| `tests/nexus_agent/mcp/test_mcp.py` | 8 | MCP client/server/transport |
| **Total** | **~158** | |

**Known gap:** Per `FRESH_AUDIT.md`, many modules lack test coverage (>80% gap in some areas). The agent loop, tool system, GUI server, and LLM providers need comprehensive testing.

---

## 12. Hardware Acceleration Matrix

| Backend | GPU/NPU Types | Install Extra | Status |
|---------|---------------|---------------|--------|
| **CUDA** | NVIDIA GPUs | `[cuda]` | ✅ Supported via llama.cpp |
| **Vulkan** | AMD, Intel, NVIDIA GPUs | `[vulkan]` | ✅ Supported via llama.cpp |
| **ROCm** | AMD GPUs (Linux) | `[rocm]` | ✅ Supported via llama.cpp |
| **Metal** | Apple Silicon (macOS) | `[metal]` | ✅ Supported via llama.cpp |
| **SYCL** | Intel GPUs (oneAPI) | `[sycl]` | ✅ Supported via llama.cpp |
| **OpenVINO** | Intel CPU/GPU/NPU | `[openvino]` | ✅ Supported via llama.cpp |
| **NPU (DirectML)** | Qualcomm Hexagon, Intel NPU | `[npu]` | ❌ ONNX engine is a stub |
| **TPU** | Google Edge TPU via JAX | `[tpu]` | ⚠️ Not viable for LLM inference (noted in docs) |

---

## 13. Known Issues & Gaps (from FRESH_AUDIT.md)

### P0 (Critical — Must Fix Before Production)
1. **ONNX Engine is a stub** — `onnx_engine.py` has no actual inference implementation. NPU support through DirectML does not work.
2. **Shell command injection risk** — Potential edge case with `shell=True` in sandbox.
3. **Missing error handling** in several tool implementations — unhandled exceptions could crash the agent.

### P1 (High — Should Fix)
1. **`local_engine.py` too large** — 839 lines needs splitting into focused modules.
2. **`agent.py` `run()` too large** — 150+ line method needs decomposition.
3. **`gui/server.py` too monolithic** — 565 lines handling API, WebSocket, and static file serving.
4. **Docker sandbox fallback absent** — Assumes Docker is installed.
5. **Tests missing for core modules** — Agent loop, tools, GUI, and LLM providers lack coverage.

### P2 (Medium)
1. **No provider latency tracking** — Smart Router cannot optimize provider selection.
2. **No `__init__.py` in `tools/`, `memory/`, `session/`** — Import path inconsistencies.
3. **Windows-first bias** — Linux/macOS may have path and shell issues.

### P3 (Low)
1. **Documentation drift** — Some docs reference old file paths or missing components.
2. **Training module is empty scaffolding** — No actual training implementation.

---

## 14. Documentation Map

| Document | Path | Description |
|----------|------|-------------|
| **CONTEXT.md** | `docs/CONTEXT.md` | Main project context & continuation guide (100+ sections). Comprehensive overview, architecture, directory tree, key technical decisions, implementation status by phase, dependency map, continuation prompt for AI agents. |
| **ARCHITECTURE.md** | `docs/ARCHITECTURE.md` | High-level architecture, directory structure, agent loop description, LLM provider interface, memory architecture, tool system, CLI vs GUI comparison, config layering, data directories, MCP integration, session system, security model. |
| **MEMORY.md** | `docs/MEMORY.md` | Chronological implementation memory log (516 lines) — 6 sessions documenting every decision, action, and rationale. Designed for LLM agents to continue development seamlessly. |
| **ROADMAP.md** | `docs/ROADMAP.md` | Detailed execution roadmap (197 lines) with 4 phases (A-D), effort estimates (~97 hours total), and post-launch plans. |
| **FRESH_AUDIT.md** | `docs/FRESH_AUDIT.md` | Comprehensive file-by-file audit (773 lines) comparing claimed vs actual implementation status. Rates project at ~60% production-ready with P0-P3 issues cataloged. |
| **AUDIT_REPORT.md** | `AUDIT_REPORT.md` | Additional audit findings at project root. |
| **API.md** | `docs/API.md` | Complete REST API + WebSocket + MCP protocol reference (379 lines). |
| **SECURITY.md** | `docs/SECURITY.md` | Security model, vulnerability reporting, sandbox details, secrets scanning (140 lines). |
| **CONTRIBUTING.md** | `docs/CONTRIBUTING.md` | Development setup, code style, type annotations, adding providers/tools, writing tests, git workflow (260 lines). |
| **README.md** | `README.md` | Main user-facing documentation with features, architecture diagram, quick start, configuration reference, supported providers list. |
| **examples/** | `docs/examples/` | 4 guides: Getting Started, Local Models, Cloud Providers, CLI Reference. |
| **REQUIREMENTS.md** | `REQUIREMENTS.md` | Additional requirements documentation. |
| **CUSTOM_INFERENCE_SERVER.md** | `docs/CUSTOM_INFERENCE_SERVER.md` | Custom inference server setup guide. |
| **task.md** | `docs/task.md` | Task tracking document. |
| **implementation_plan.md** | `docs/implementation_plan.md` | Original implementation plan. |
| **Offline Localized AI Agent.md** | `docs/Offline Localized AI Agent.md` | Offline AI agent concept document. |

---

## 15. Project Metadata

| Field | Value |
|-------|-------|
| **Name** | `nexus-agent` |
| **Version** | `0.1.0` |
| **Status** | Development Status :: 3 - Alpha |
| **License** | MIT |
| **Python Version** | >= 3.10 |
| **CLI Entry** | `nexus` (via `nexus_agent.__main__:main`) |
| **Source** | `src/` directory |
| **Keywords** | llm, agent, coding, offline, cli, gui |
| **Classifiers** | Code Generators, Artificial Intelligence |
| **Repository** | `https://github.com/nexus-agent/nexus-agent` |
| **Documentation** | `https://nexus-agent.readthedocs.io` |
| **Install (Windows)** | `irm https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.ps1 \| iex` |
| **Install (Linux/macOS)** | `curl -LsSf https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.sh \| sh` |
| **PyPI** | `pip install nexus-agent` |
| **Primary Interface** | `nexus chat` (TUI) or `nexus gui` (Web) |

---

*End of Report*
