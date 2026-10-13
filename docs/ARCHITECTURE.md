# NexusAgent Architecture

> **Version:** 0.3.0-alpha.5  
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

The intended governance target is main as the canonical integration branch, but the live repository state checked on 2026-10-13 reports master as the default branch and main also exists. Resolve that default-branch migration and the split PR targets before treating main as the active canonical branch. The branch listing reported both branches as unprotected; the rulesets endpoint was empty, and the integration could not read branch-protection settings (HTTP 403). A repository administrator must verify and apply the policy.

Runtime changes, research behavior, native clients and release infrastructure must be validated through GitHub Actions against the exact candidate commit rather than depending only on local validation. The intended merge-quality surface consists of the Python test matrix, Ruff/MyPy checks, native Rust/desktop checks, version synchronization, audit evidence generation, CodeQL and dependency security checks. Release tags must be verified to point into the history of the verified canonical integration branch before publication.

Branch-protection policy is documented in .github/BRANCH_PROTECTION.md; documentation alone does not enforce GitHub settings.

**Runtime exposure guard (2026-10-13):** The GUI/API startup path rejects non-loopback bind addresses before model/runtime initialization while authenticated identity and tenant isolation are unqualified. Loopback-only request checks are a local-mode safeguard, not proof of authenticated multi-user authorization. Do not re-enable LAN/shared binds until Gate 2 passes its ownership, secret isolation, worker authorization and cross-tenant negative-test requirements.


## Authoritative target architecture and language decision (2026-10-13)

This section is the current target decision and supersedes conflicting older planning statements. It is based on NexusAgent's product requirements, not on the languages or modules currently present in the repository. It defines the desired boundaries; it does not authorize a wholesale rewrite without an incremental migration plan.

### Product and deployment boundary

NexusAgent must support both local/personal deployment and authenticated multi-user deployment from the initial architecture. “Local-first” describes the ability to run locally and use local models/tools; it does not mean the runtime may assume a single trusted user or that all control APIs can remain unauthenticated loopback-only endpoints.

Deployment profiles may differ in packaging and infrastructure, but share the same domain contracts. Multi-user deployment must not be exposed until identity, authorization, tenant/workspace isolation, secret isolation, audit trails, quotas and recovery semantics pass security qualification.

### Recommended language allocation

- **Python — primary agent, orchestration and research runtime.** Best overall fit for model/provider ecosystem breadth, research/data processing, local-inference integration and fast iteration on agent behavior. Use asynchronous I/O for network/tool-bound concurrency, explicit worker/resource limits, process isolation where appropriate, and typed/validated boundaries.
- **TypeScript — web frontend.** Use for interactive workflow visualization, activity streams, forms and browser-side state. Share generated/versioned API schemas rather than duplicating domain logic in the UI.
- **Rust — native desktop/CLI and narrowly scoped system-sensitive services.** Use where native packaging, memory safety or predictable resource use justify it. Keep orchestration and provider semantics in the shared runtime unless benchmarks or security analysis establish a compelling reason to move a specific component.
- **Language-neutral contracts — API and event envelopes.** Define versioned request/response schemas, canonical IDs, error shapes, event types and compatibility rules. Do not use an implicit in-process object model as the contract between clients or services.

If the agent/orchestration core must use exactly one language, choose Python. Rust is not the best sole language for this entire product because model, research and tool ecosystems and iteration speed dominate the core's trade-offs; TypeScript is not the best sole core language because local inference and research/data-processing integration are central; Go is a credible backend alternative but does not outweigh Python's agent/research ecosystem for this requirement set. This is a requirements-based recommendation, not a statement that current repository code proves the choice.

References: [Python asyncio](https://docs.python.org/3/library/asyncio.html), [official MCP SDK tiers](https://modelcontextprotocol.io/docs/sdk), [official Rust MCP SDK](https://github.com/modelcontextprotocol/rust-sdk).

### Required logical boundaries

1. **Identity and policy:** authentication, tenant resolution, roles, workspace membership and policy evaluation.
2. **Application/API:** versioned client contracts; request validation; idempotency for mutating requests; rate/resource limits.
3. **Run/session service:** lifecycle, cancellation, resume/recovery and ownership checks.
4. **Orchestration:** bounded planning, dependency DAG, dynamic profile generation, scheduling and result verification.
5. **Agent execution:** isolated per-run/per-worker context, scoped memory and tool grants.
6. **Provider/model adapters:** provider-neutral capabilities, secret references, timeouts, retry budgets and normalized errors.
7. **Tool/MCP gateway:** schema validation, effective authorization, destination/path controls, sandboxing, audit events and bounded execution.
8. **Persistence:** durable relational records for users/tenants/workspaces/runs/tasks/events; artifact storage with ownership and containment; memory partitioning and migrations.
9. **Event delivery:** durable or replayable ordered events with stable IDs, run/tenant ownership and reconnect support.
10. **Clients:** web, CLI/TUI and native desktop; no client bypasses shared policy or implements its own orchestration semantics.

### Multi-user invariants

- Every tenant-owned row, artifact, memory record, run, message and event has an explicit ownership boundary.
- Authorization is checked server-side on every read, write, download, cancellation and resume operation.
- Credentials are scoped to the owning user/tenant or explicitly shared by authorized policy; they are never copied into prompts, logs or generated profiles.
- A task cannot read another tenant's data by guessing identifiers or manipulating paths, filters, URLs or artifact references.
- One user's resource exhaustion cannot indefinitely starve other tenants; enforce per-tenant concurrency and resource budgets.
- Local single-user mode uses the same authorization-aware domain services, with a documented local identity/bootstrap policy.
- Background workers revalidate ownership and authorization; API checks alone are insufficient.
- Audit logs must avoid storing secrets and must distinguish actor, tenant, action, target and outcome.

### Completion standard

Architecture claims are targets until verified against code and tests. Each target capability needs traceable acceptance tests and workflow evidence. Any migration from existing code must preserve behavior through adapters/contracts, proceed gate by gate, and avoid parallel implementations of the same domain logic.
