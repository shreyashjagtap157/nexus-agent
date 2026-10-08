# NexusAgent Architecture

> **Version:** 0.3.0-alpha.4  
> **Status:** Active Alpha / multi-agent platform integration hardening  

---

## 1. High-Level Architecture

NexusAgent is a local-first agentic workbench combining single-agent coding/research sessions with dynamically assembled multi-agent teams. It provides CLI/TUI, a local web UI, and a native Rust client over a shared Python runtime.

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                 │
│            (Terminal / Browser / API Client)                 │
└──────────────────┬───────────────────────┬──────────────────┘
                   │                       │
          ┌────────▼────────┐   ┌──────────▼──────────┐
          │   CLI (TUI)     │   │     GUI (Web)        │
          │   Textual       │   │     FastAPI          │
          │   + Rich        │   │     + WebSocket      │
          └────────┬────────┘   └──────────┬──────────┘
                   │                        │
                   └────────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │    Agent Core        │
                    │    (AgentLoop)       │
                    │    + Orchestrator    │
                    └───┬─────┬─────┬──────┘
                        │     │     │
          ┌─────────────┘     │     └─────────────┐
          │                   │                   │
     ┌────▼────┐  ┌──────────▼───┐  ┌──────────▼────┐
     │  Tools  │  │  LLM Backend │  │    Memory      │
     │file,git,│  │ local + cloud │  │  W/LT/Ep/UP    │
     │shell,lsp│  │   providers   │  │                │
     │edit,web │  └───────────────┘  └────────────────┘
     └─────────┘
```

---

## 2. Directory Structure

```
nexus_agent/
├── __init__.py               # Package init + version
├── __main__.py               # CLI entry: nexus chat/gui/model/session/config/hardware/wizard
│
├── core/
│   ├── agent.py              # AgentLoop — gather→act→verify cycle
│   ├── config.py             # Multi-layer config loader
│   ├── context.py            # Auto-compaction context manager
│   ├── sandbox.py            # Sandboxed command execution
│   ├── orchestrator.py       # Planner→Executor sub-agent orchestration
│   ├── planner.py            # Planner sub-agent
│   ├── executor.py           # Executor sub-agent
│   ├── task_graph.py          # Hierarchical task DAG
│   ├── nla_telemetry.py      # Reasoning telemetry logging
│   ├── debate.py             # Multi-agent debate consensus
│   └── devops.py             # Local CI pipeline (lint/test/secret checks)
│
├── llm/
│   ├── base.py               # LLMProvider abstract interface
│   ├── local_engine.py       # llama-cpp-python GGUF engine
│   ├── model_manager.py       # GGUF discovery + hardware detection
│   ├── runtime_manager.py    # Runtime selection (llama.cpp, ONNX, Ollama)
│   └── providers/            # Cloud provider implementations
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── google_provider.py
│       ├── groq_provider.py
│       ├── deepseek_provider.py
│       ├── openrouter_provider.py
│       ├── ollama_provider.py
│       ├── aws_bedrock_provider.py
│       └── custom_openai_provider.py
│
├── memory/
│   ├── memory_manager.py      # Orchestrates all memory subsystems
│   ├── working_memory.py      # In-memory LRU scratchpad
│   ├── long_term.py          # SQLite FTS5 persistent recall
│   ├── episodic.py           # Session history with FTS5
│   └── user_profile.py        # YAML-backed preference learning
│
├── tools/
│   ├── base.py               # Abstract Tool class
│   ├── file_ops.py           # Read, Write, Search, ListDirectory
│   ├── shell.py              # Sandboxed shell execution
│   ├── code_edit.py          # Search-replace + insert
│   ├── git_ops.py            # Git operations + SmartCommit
│   ├── web_search.py         # DuckDuckGo search
│   ├── lsp_client.py         # LSP diagnostics
│   └── browser.py            # Playwright + HTTPX browser
│
├── skills/
│   ├── skill_loader.py       # Markdown .md skill parser
│   ├── skill_registry.py     # Skill registry + tool exposure
│   └── builtin/              # Built-in skill definitions
│
├── mcp/
│   ├── client.py             # MCP stdio client
│   ├── server.py             # MCP stdio server
│   └── transport.py          # JSON-RPC 2.0 stdio transport
│
├── session/
│   ├── manager.py            # Session lifecycle management
│   ├── storage.py            # SQLite session storage
│   └── checkpoint.py         # Git-worktree checkpoint/rollback
│
├── permissions/
│   ├── manager.py            # Permission evaluation engine
│   └── rules.py              # Permission rule definitions
│
├── cli/
│   ├── app.py                # Textual TUI main application
│   ├── auth.py               # API key management
│   ├── renderer.py           # Rich-based terminal rendering
│   ├── theme.py              # Dark/light theme colors
│   ├── wizard.py             # Interactive first-run setup wizard
│   ├── file_tree.py          # Directory tree sidebar
│   ├── diff_view.py          # Syntax-highlighted diff viewer
│   ├── approval_dialog.py    # Permission approval overlay
│   └── styles.tcss           # Textual CSS styles
│
└── gui/
    ├── server.py             # FastAPI web server
    └── frontend/             # Static HTML/CSS/JS dashboard
```

---

## 3. Agent Loop (Core)

The `AgentLoop` in `core/agent.py` implements a gather→act→verify cycle:

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

---

## 4. LLM Provider Interface

All providers implement `LLMProvider` from `llm/base.py`:

```python
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...
    def get_capabilities(self) -> ProviderCapabilities: ...
    def chat_completion(messages: list[Message], tools=None, **kwargs) -> LLMResponse: ...
```

Three categories:
- **Local**: `LocalEngine` (llama-cpp-python), `OllamaProvider`, ONNX via `onnxruntime-genai`
- **Cloud**: OpenAI, Anthropic, Google, Groq, DeepSeek, OpenRouter, AWS Bedrock
- **Custom**: `CustomOpenAIProvider` for any OpenAI-compatible endpoint

---

## 5. Memory Architecture

Four-tier memory system (`memory/memory_manager.py`):

| Tier | File | Storage | Purpose |
|------|------|---------|---------|
| Working | `working_memory.py` | In-memory LRU dict | Current session scratchpad |
| Long-term | `long_term.py` | SQLite FTS5 | Persistent recall across sessions |
| Episodic | `episodic.py` | SQLite FTS5 | Session history search |
| User Profile | `user_profile.py` | YAML file | Learned user preferences |

Key operations:
- `get_context_for_prompt(query)` — merges relevant context from all tiers
- `search_cross_memory(query)` — queries across all tiers
- `save_session_summary()` — called on session end to persist summaries

---

## 6. Tool System

Tools extend `base.py`'s `Tool` abstract class:

```python
class Tool(ABC):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def parameters(self) -> dict: ...
    def execute(self, **kwargs) -> ToolResult: ...
```

Permission levels per tool: `allow`, `ask`, `deny`
Permission mode global setting: `suggest`, `ask`, `auto`

---

## 7. CLI vs GUI

Both interfaces share the same agent core (`AgentLoop`), memory (`MemoryManager`), and LLM backend:

```
CLI (Textual)
└─ app.py → NexusApp → AgentLoop + tools
    ↓ (same AgentLoop, different UI transport)
GUI (FastAPI + WebSocket)
└─ server.py → FastAPI + uvicorn → AgentLoop + tools
```

---

## 8. Config Layering (Priority High→Low)

```
1. Default config      → nexus_agent/_default_config.yaml (package)
2. User config         → ~/.nexus-agent/config.yaml
3. Project config      → ./.nexus-agent.yaml (workspace)
4. Environment vars    → NEXUS_* prefix
5. CLI --config flag   → explicit file
6. CLI --model, --provider → programmatic overrides
```

---

## 9. Data Directories

```
~/.nexus-agent/          # User data root
├── config.yaml          # User overrides
├── models/             # GGUF/ONNX model files
├── memory/             # SQLite memory DBs
│   ├── memory.db        # Working + LT memory
│   └── episodic.db      # Session history
├── sessions/           # Session storage
│   └── sessions.db
├── skills/            # User-defined skills
└── traces/           # NLA telemetry JSONL logs
```

---

## 10. MCP Integration

Model Context Protocol via `mcp/` module:
- `StdioTransport`: JSON-RPC 2.0 over stdin/stdout
- `MCPClient`: Connects to external MCP servers
- `MCPServer`: Exposes NexusAgent tools as MCP endpoints

---

## 11. Session & Checkpoint

`SessionManager` (`session/manager.py`):
- Creates/restores sessions from `sessions.db`
- Tracks workspace git state per session
- `CheckpointManager` creates git worktree snapshots

---

## 12. Security Model

- Shell commands pass through `Sandbox` (`core/sandbox.py`)
- Sandbox uses `shlex.split()` → list args via `subprocess.run(shell=False)`
- Pattern-based `dangerous_indicators` regex for detection
- Git operations protected via worktree isolation
- API keys stored via `AuthStore` in user data dir (not in config)

## 13. Multi-agent Team Runtime

The team runtime dynamically assembles professional roles, executes isolated AgentLoops concurrently, coordinates through a persistent SQLite blackboard, and performs reviewer/synthesis passes. Dependencies execute in waves so independent workers remain parallel while dependent workers wait for prerequisites. Pause, resume and stop requests are persisted for local cross-client control.

Team outputs support chat, Markdown/text artifacts and JSON artifacts. Role-specific provider/model/fallback routing can override named team roles.

## 14. Agent Profiles and Agent Forge

Reusable Markdown agent definitions resolve from built-in, global, user, project and workspace scopes. Users can author profiles manually or ask NexusAgent to generate them from natural-language requirements. Profiles can be pinned into teams or executed directly with nexus agent run.

## 15. Scoped Memory

The existing hybrid memory system is exposed through explicit global, user, project, workspace, agent, team and session scopes. Team workers retrieve relevant prior context and can persist completed findings to agent/team memory.

## 16. Evidence-first Research

Research teams support configurable depth from glance through maximal, source seeding, a persistent source registry, source snapshots, claim/evidence records and deterministic quotation verification.

## 17. Provider and Authentication Plane

Provider metadata, model/endpoint configuration and credentials are separate concerns. AuthStore supports an OS keychain when available and a permission-restricted file fallback. Role-level provider/model/fallback configuration is resolved before generic team defaults.

## 18. Universal Tool Plane

CLI, web, native and team workers share filesystem mutation/recovery, shell, Git/CI, web/browser, LSP, code intelligence, RAG, memory, delegation/council and MCP tools.

## 19. Runtime Storage and File Governance

Persistent user state, project configuration and workspace runtime state are deliberately separated. File mutations are journaled with hashes where applicable; deletes default to reversible runtime trash. Git metadata paths and workspace escapes are explicitly rejected by file mutation tools.


## 20. Formal Verification Plane

The shared tool plane includes `formal_check`, which invokes explicitly supported local
verifiers without a shell. Supported adapters include Z3, Lean, Lake/Lean, Rocq/Coq,
Dafny, TLC, Apalache, Alloy and K Framework when their executables are installed.

Formal verification results are runtime evidence. Missing verifier executables are reported
as unavailable; informal LLM reasoning is never relabeled as a machine-checked proof.

## 21. Research Coordination Contract

Research planning is a one-time deployment phase. After the specialist team is deployed,
the execution scheduler uses 5–10 dependency-aware coordination waves according to the
selected research depth. Deeper levels increase source breadth, verification, contradiction,
formal-analysis and review budgets within those waves rather than creating unbounded planning
iterations.

The final research synthesis is evidence-bound: it consumes verified ledger claims, requires
valid `[claim:N]` provenance markers and is withheld when the evidence or contradiction gates
do not pass.


## 22. Engineering and CI Governance

The repository treats main as the canonical integration branch. Runtime changes, research behavior, native clients and release infrastructure are validated through GitHub Actions rather than depending on a local validation result.

The merge-quality surface consists of the complete Python test matrix, Ruff/MyPy checks, native Rust/desktop checks, version synchronization, audit evidence generation, CodeQL and dependency security checks. Release tags are independently verified to point into main history before publication.

Branch protection policy is maintained in .github/BRANCH_PROTECTION.md and is enforced at the GitHub repository-administration layer.
