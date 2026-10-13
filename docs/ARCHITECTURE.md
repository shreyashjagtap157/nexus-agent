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

**Runtime exposure guard (2026-10-13):** The GUI/API startup path rejects non-loopback bind addresses before model/runtime initialization while authenticated identity and tenant isolation are unqualified. Browser-originated API requests must match the exact loopback origin, and WebSocket origin checks reject foreign origins. Loopback and origin checks are local-mode/CSRF safeguards, not proof of authenticated multi-user authorization. Do not re-enable LAN/shared binds until Gate 2 passes its ownership, secret isolation, worker authorization and cross-tenant negative-test requirements.


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

The detailed proposed principal, tenant, session, local-bootstrap and migration contract is maintained in `docs/STORAGE_AND_GOVERNANCE.md` under “Gate 2 principal, tenant and session contract”. Treat that contract as a pre-exposure implementation requirement; it is not proof that current runtime code already enforces the model.

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

## Exhaustive implementation blueprint (authoritative review, 2026-10-13)

### Decision status and scope

This section translates the target architecture above into implementable boundaries, migration order and acceptance tests. It does not claim that target components already exist. The live codebase is a Python runtime with FastAPI, provider/tool/memory/research/team modules; it also contains a Python CLI, a static HTML/CSS/JavaScript web frontend, a Rust CLI/TUI, and a Rust eframe desktop client. The web frontend is not yet a TypeScript application, and the target multi-user identity/tenant model is not yet qualified.

The current version baseline is 0.3.0-alpha.5. As observed on 2026-10-13, GitHub still reports master as the repository default while main exists separately. Use the live repository state and current workflows as evidence; do not assume the branch migration or branch protections have been applied.

The architecture decision is to keep one authoritative domain runtime and put client-specific presentation outside it. The objective is not to maximize the number of languages, frameworks, services or abstractions. Every additional boundary must earn its cost through isolation, performance, packaging, reliability or maintainability.

### 1. Programming-language allocation

| Area | Language and recommended stack | Responsibility | Current state and migration rule |
|---|---|---|---|
| Agent runtime and domain services | Python, typed gradually with strict checks on critical modules | Runs, planning, workers, policies, tools, providers, research, memory and workflows | This is the existing core. Keep it authoritative; refactor by boundary, not rewrite. |
| HTTP API | Python, FastAPI, Pydantic request/response models | Authentication dependencies, schema validation, policy calls, run/session endpoints, health and admin operations | Existing FastAPI surface is useful but mostly unversioned and local-first. Harden it, then migrate clients through adapters. |
| Scheduling and research | Python | Dependency DAG, bounded planner, tool execution, source capture, evidence checks, synthesis and stopping rules | Existing team/research modules should be incrementally made run-scoped, durable and testable. |
| Provider adapters and local inference | Python | Hosted API adapters, OpenAI-compatible endpoints, NVIDIA NIM, local GGUF/ONNX/Ollama integration, retry/timeout normalization | Keep the current provider layer as the single source of truth. Do not duplicate provider semantics in Rust. |
| Tool and MCP gateway | Python | Tool schemas, effective permission evaluation, MCP client integration, policy enforcement, sandbox dispatch and audit events | Extend the shared tool plane. A prompt, agent profile or client must never grant itself permissions. |
| Persistence/domain repositories | Python + SQL; SQLite locally and PostgreSQL for shared multi-user deployments | Durable records, transactional state transitions, ownership filters and migrations | Existing SQLite stores remain suitable for local/offline operation. Introduce production-grade tenant-aware repositories before shared deployment. |
| Web application | TypeScript + React + Vite; a shared component system and accessible design tokens | Workflow graph, agent builder, activity timeline, task controls, provider/configuration screens, memory/research inspection and responsive UX | Target modernization only: current web files are static HTML/CSS/JavaScript. Migrate one screen at a time and keep FastAPI as the backend. |
| Native CLI/TUI | Rust, retaining the existing Rust workspace and TUI framework | Process lifecycle, terminal input/rendering, keyboard handling, local configuration UI and robust backend-client behavior | Continue using the current Rust client over a documented protocol. Do not move planning, policy or provider routing into it. |
| Native desktop | Rust with the existing eframe client | Desktop shell, windowing, navigation, notifications and API/event consumption | Treat it as a client of shared contracts, not a second application core. |
| Cross-language client contracts | OpenAPI-generated TypeScript types/client plus explicit JSON event envelopes; documented NDJSON/JSON-RPC only where subprocess IPC is required | Stable API/event schemas, compatibility and client parity | Existing in-process Python object shapes are not cross-process contracts. Generate or validate client types from one source. |
| Build, CI and release automation | GitHub Actions YAML, shell/PowerShell and Python/Rust build tools | Repeatable checks, packaging, supply-chain evidence and release provenance | Keep the workflow reproducible and tied to the exact candidate commit. |

**Python is the one-language choice for the agent backend.** It offers the most practical fit for fast-changing model/provider integrations, local inference bindings, web/research/data processing, and the existing codebase. This is not a claim that Python automatically provides concurrency or isolation: use bounded async I/O, finite worker pools, process isolation for risky or CPU-bound work, and explicit resource limits.

**TypeScript is for the web UI, not a second backend.** React is the recommended component model, Vite is sufficient for a compiled single-page application, and TypeScript types should be generated from the API contract rather than manually copied. The initial migration does not require Next.js or server-side rendering: the app can be built as static assets and served by the existing FastAPI deployment. Adopt a more complex web framework only if an evidenced requirement appears.

**Rust is for native presentation and selected system boundaries, not the orchestration core.** The Rust CLI/TUI and eframe desktop client are real existing investment. Use them for terminal rendering, native packaging, process supervision, OS integration and predictable client behavior. They should consume the same HTTP/WebSocket contracts or an explicitly versioned local IPC protocol. Do not reimplement the Python planner, tenant authorization, memory semantics, provider catalog or team scheduler in Rust.

**Do not move inference dispatch to Rust merely to avoid the Python GIL.** Most hosted model latency is network/provider-bound, and local inference cost depends heavily on the inference engine, GPU backend, model, context and quantization. The existing Python local engine already calls native inference code. A Rust inference adapter is a future option only if reproducible benchmarks identify a material bottleneck and the proposed adapter passes behavioral parity tests.

Do not add Go, a Rust web server, a TypeScript backend, or additional microservices now. No additional language improves the current domain boundaries enough to justify duplicated logic and build/release complexity. SQL and deployment configuration are supporting technologies, not separate application runtimes.

### 2. Logical architecture and ownership of responsibilities

Implement these as logical boundaries inside the current repository first. Split them into processes or deployable services only when an explicit threat, scaling or availability requirement warrants it.

**Immediate code findings that must shape the first implementation slices:**

- The live GUI server has a process-global StateManager containing workspace, config, engine, memory manager, session manager, permission manager and active-session state. Treat these as single-process bootstrap services or defaults, not as per-user/per-run mutable context. The first multi-user-capable refactor must move current actor, selected workspace, provider route and active run/session into explicit request/run context.
- The WebSocket endpoint accepts a session ID in its URL and updates the global active-session field, but the shared SessionManager has its own single mutable _active_session_id. Its save_message, auto_title, file-change tracking and checkpoint operations target that internal active ID. These two active-session concepts are not an ownership-safe binding. Add a regression test with two sessions and interleaved messages before changing the code; then pass the authorized session ID explicitly through service calls instead of switching a shared active ID around each request.
- The team runtime constructs workspace tools around a selected workspace and stores team records in a SQLite database whose current schema identifies teams but does not establish a tenant/user ownership relation. This is workable for local personal mode, but is not a shared multi-user boundary. Keep the local adapter and add ownership-aware repository/service contracts before hosted mode.
- The current Python team runtime uses a bounded ThreadPoolExecutor-style worker approach and workspace-local SQLite stores. Preserve it as the local execution adapter, but do not assume threads or workspace folders provide process isolation, durable queue leases or tenant separation.

Prioritize tests that prove these are isolated before broad service extraction. A security contract is only useful when the regression suite would fail against the unsafe behavior.

1. **Identity and policy:** validate a local principal or authenticated session; resolve the active tenant/workspace from server-side records; check membership, role and resource-specific grants; return an auditable allow/deny decision. Never trust a tenant ID supplied in a body/header as authority.
2. **API/application layer:** parse versioned requests, validate limits, apply idempotency to suitable mutations, call domain services, translate typed domain errors into stable HTTP errors, and never contain orchestration loops.
3. **Run/session service:** create runs, record requester and ownership, capture a configuration snapshot, issue cancellation/resume requests, expose authorized state and recover interrupted runs.
4. **Planner and workflow registry:** translate a goal into a validated DAG; select saved agent profiles; generate missing profiles only within limits; reject unknown dependencies/cycles; record the approved plan before starting side effects.
5. **Scheduler and worker supervisor:** claim ready tasks, obey tenant and global concurrency limits, lease work, monitor timeouts/heartbeats, propagate cancellation and persist final outcomes. Every retry must be bounded and justified by a retryable failure class.
6. **Agent execution:** create an independent run/task context with the assigned role, permitted tool handles, provider route, budget and scoped memory. Do not pass mutable process-global state to parallel workers.
7. **Tool/MCP gateway:** validate tool arguments against schemas; derive effective permission from the authenticated principal, tenant/workspace, run, agent grants, tool risk and current policy; execute with bounded privileges; redact outputs; record audit events.
8. **Provider and credential plane:** resolve the model/provider/fallback for the role, retrieve a secret reference through the authorized credential store, apply timeout/rate-limit/retry/cost policy and normalize provider errors.
9. **Research/evidence plane:** capture provenance-bearing source snapshots, quotes, claims, verifier decisions, contradictions and quality-gate outcomes. Keep evidence records separate from an LLM's unsupported assertions.
10. **Persistence and artifact plane:** own transactions, migrations, row ownership, artifact metadata, storage containment and retention. Domain services use repository interfaces rather than opening databases ad hoc.
11. **Event and observability plane:** append durable ordered events before notifying subscribers; support reconnect/replay; emit correlated logs, metrics and traces with secret-safe structured fields.
12. **Client adapters:** the web UI, Rust CLI/TUI, desktop client and automation/MCP entrypoints display state and send commands. They do not own policy decisions or create an alternative scheduler.

### 3. End-to-end run lifecycle

The ordinary run path should be deterministic enough to inspect and recover:

1. The client submits a goal, workspace selection, execution mode, output preference and optional provider/agent overrides to the API.
2. The API resolves the actor and tenant from a verified local identity/session, authorizes workspace access and validates the request against tenant/user limits.
3. The run service creates a run record and immutable configuration snapshot. An idempotency key prevents duplicate run creation on client retries.
4. The planner uses the goal, selected workflow and allowed agent registry to produce a typed DAG. It validates dependency references, cycles, duplicate/contradictory responsibilities, writable capabilities and budget estimates.
5. Policy validation rejects or narrows any requested capability that exceeds the actor's grants. Approval-required work is represented as an explicit waiting state; an agent prompt cannot bypass that state.
6. The scheduler persists the plan, task rows and dependency edges, then claims only ready tasks within global and tenant concurrency/budget limits.
7. Each worker receives an immutable task input plus a fresh mutable context, provider route, bounded memory view, permission-filtered tools, cancellation signal and budget account. It does not receive credentials belonging to unrelated actors.
8. Before each tool call, the gateway validates the arguments, checks the current permission decision, enforces path/network/process policy, applies timeout/output limits, records the attempt and executes the tool.
9. Worker results, messages, artifacts, state transitions and tool outcomes are committed to durable storage. Events are appended in sequence and published only after persistence succeeds.
10. Independent verifier/reviewer passes check output correctness, claims, artifact integrity, policy compliance and unresolved failures. Research work additionally passes the evidence/contradiction gate.
11. The run reaches one canonical terminal outcome. A successful worker alone does not mean a run succeeded if required verification failed; explicit states such as needs-review or partially-completed should not be disguised as success.
12. Clients can reconnect and reconstruct current state from the snapshot plus events after a known sequence/ID. A resume request must be re-authorized against the run owner, tenant and current membership.

The scheduler must never loop indefinitely because a planner or worker requests another round. Enforce hard maxima on plan revisions, agents, dependency waves, concurrency, tool calls, retries, wall-clock time, token/cost spend and artifact size. For research, the selected depth changes these budgets and verifier/contradiction requirements; it must not merely change prompt wording.

### 4. Domain records and persistence strategy

The relational source of truth should eventually represent at least the following concepts. Names are conceptual; migrate existing tables through repository adapters rather than creating parallel versions of every existing store.

- **Identity:** users/service principals, tenants, memberships, roles and revocations.
- **Workspace:** tenant owner, canonical workspace identifier, local-path mapping if in local mode, grants and lifecycle state.
- **Configuration:** tenant/user/project configuration revisions, provider/model references, policy revision and run snapshots.
- **Agents and workflows:** profile identity, scope/owner, version, validated schema, declared capabilities, reviewer flag, dependencies and workflow version.
- **Runs and tasks:** run owner/tenant/workspace, requester, goal reference, status, plan revision, resource budget, timestamps, cancellation state and final result.
- **Task graph:** task rows, dependency edges, attempts, worker leases, checkpoints and verification results.
- **Conversation and collaboration:** messages, agent-to-agent messages, explicit recipients/scope, tool invocation references and session metadata.
- **Events and audit:** stable event ID, per-run sequence, actor, tenant/resource ownership, event type, outcome, time and correlation/trace IDs; separate security audit records from verbose debug logs.
- **Artifacts and source evidence:** opaque artifact IDs, owning tenant/workspace/run, normalized relative name, content hash, size, media type, storage key, retention status, source URL/snapshot metadata and verified claims.
- **Memory:** scope, owner, tenant/workspace/agent/team/session association, content classification, provenance, retention/expiry and searchable representation.
- **Secrets:** non-secret credential metadata and a reference to a secret provider. Raw secret values are not ordinary configuration rows and do not enter prompts or artifact exports.
- **Usage/quotas:** per-tenant/user run slots, tokens/cost, tool runtime, artifact storage, rate counters and policy revisions.
- **Idempotency and approvals:** caller/key/resource/result for deduplicated mutations; approval requester, approver, allowed action, scope, expiry and consumed status.

**Local mode:** retain a small single-user SQLite footprint for offline use and existing workspace-local runtime files. Preserve current data layout where practical; add explicit ownership metadata and migrations rather than requiring users to lose or manually rebuild their history.

**Shared multi-user mode:** use PostgreSQL as the transactional source of truth. The local SQLite store is not the primary shared-server concurrency/ownership strategy. Recommended data-access target: SQLAlchemy 2.x typed models/repositories plus Alembic schema migrations for ownership-critical and shared tables. Use async database sessions on the async API path and never share a session/connection across tasks or threads; if a transitional synchronous repository is called, run it in a bounded worker and keep its transaction/session local to that worker. Do not mix hand-written SQL and ORM access to the same table without one documented repository owner. Migrate the run/tenant/workspace/event/artifact ownership path first, then migrate lower-risk stores as tested adapters allow; do not rewrite every local SQLite store in one step. Test the same logical repository contracts against SQLite and PostgreSQL where their behavior differs. Use database constraints and transactions as well as service-level ownership checks. PostgreSQL row-level security may be added as defense in depth, but it does not replace application authorization, review of privileged database roles or negative tests.

**Artifacts:** introduce an ArtifactStore interface with a local filesystem adapter for personal use and a private object-store adapter for a hosted deployment when needed. Keep metadata and tenant ownership in the database. Use canonical path containment, symlink handling, safe generated storage keys, maximum-size rules, content-type handling and retention/deletion policy. An opaque or random ID is a locator, never authorization.

**Transactions and migrations:** use versioned schema migrations, foreign keys, uniqueness constraints and explicit transaction boundaries. Multi-row state transitions such as run creation, task creation and event append must be atomic where needed. Test backup/restore, upgrade from a supported previous schema, concurrent writers, crash recovery and interrupted migrations.

**Memory:** preserve the existing scopes but resolve access by principal/tenant/workspace before retrieval. A user-scoped entry must never become visible to every user simply because the process shares one memory directory. Retrieval ranking, embeddings or full-text search happen only after the authorized candidate set is determined. Treat imported documents and retrieved memory as untrusted input and retain provenance/retention metadata.

#### 4.1 Suggested canonical relational model

The following is a logical schema target for migrations and repository contract tests, not a literal SQL migration to apply before examining existing data. Use immutable UUID/ULID-like primary keys, UTC timestamps, explicit foreign keys and bounded indexed query patterns. Keep provider credentials outside ordinary rows; store only a secret reference.

| Relation | Minimum ownership/identity columns | Important constraints and purpose |
|---|---|---|
| `principals` | `principal_id`, `kind`, `status`, `created_at` | Stable human/service identity; display name is never an authorization key. |
| `tenants` | `tenant_id`, `status`, `created_at` | Top-level quota and security boundary. |
| `tenant_memberships` | `tenant_id`, `principal_id`, `role`, `status`, `valid_until` | Unique principal/tenant pair; status and expiry checked on requests and worker claims. |
| `workspaces` | `tenant_id`, `workspace_id`, `owner_principal_id`, `storage_key`, `status` | Unique storage key within its namespace; hosted mode must not accept an arbitrary client path as authority. |
| `sessions` | `tenant_id`, `session_id`, `owner_principal_id`, `workspace_id`, `status`, timestamps | Messages and checkpoints refer to an explicitly owned session. |
| `runs` | `tenant_id`, `run_id`, `requester_principal_id`, `workspace_id`, `session_id`, `status`, `plan_revision`, `config_snapshot`, `budget`, `idempotency_key` | Unique tenant/idempotency key; contains enough data to recover without trusting the client. |
| `tasks` | `tenant_id`, `task_id`, `run_id`, `status`, `attempt_count`, `deadline_at`, `lease_owner`, `lease_expires_at` | Index ready tasks and lease expiry; each task belongs to an authorized run/tenant. |
| `task_dependencies` | `tenant_id`, `run_id`, `task_id`, `depends_on_task_id` | Composite uniqueness; both dependency endpoints belong to the same run; detect cycles before dispatch. |
| `worker_attempts` | `tenant_id`, `attempt_id`, `task_id`, lease data, timestamps, result/error category | Immutable attempt history; exclude secrets and unlimited tool output. |
| `messages` | `tenant_id`, `message_id`, `run_id` or `session_id`, `sender_id`, optional recipient, type, bounded payload/reference | Read through an authorized run/session; broadcast only inside the permitted team/run. |
| `run_events` | `tenant_id`, `run_id`, `sequence`, `event_id`, `event_type`, timestamp, safe payload | Unique `(run_id, sequence)` and `event_id`; append-only application behavior; owner-checked replay. |
| `artifacts` | `tenant_id`, `artifact_id`, `run_id`, `workspace_id`, `storage_key`, relative name, media type, size, hash, retention/deletion status | Unique storage key; never derive storage paths from untrusted IDs/names; re-check ownership on every download. |
| `memory_entries` | `tenant_id`, `entry_id`, scope, owner/workspace/run/session references, provenance, classification, expiry | Filter candidate records by authorized scope before ranking/search. |
| `provider_connections` | `tenant_id`, connection ID, owner, sharing policy, provider/model metadata, `secret_ref` | Sharing is explicit and auditable; raw secret values stay in a dedicated secret store. |
| `agent_profiles` | `tenant_id` where tenant-scoped, profile ID, scope/owner, version, content hash, declared capabilities | Built-in global profiles are an explicit immutable scope, not an accidental default. |
| `approvals` | `tenant_id`, approval ID, requester/approver, run/task/action/target, expiry, consumed state | Approval bound to exact action and target; single-use and expiry checked. |
| `audit_events` | tenant, actor, action, target, outcome, policy version, timestamp, correlation ID | Append-only access; avoid tokens, secrets or unlimited prompt payloads. |
| `idempotency_records` | tenant, principal, operation, key, request fingerprint, response/resource reference, expiry | Reuse with a different request fingerprint is a conflict. |

**Tenant-aware query rule:** repositories expose methods such as `get_run(principal, run_id)`, `list_runs(principal, filters, cursor)` and `cancel_run(principal, run_id)`, not public methods that trust an arbitrary tenant ID. Verified principal context and current membership determine authorized tenants; the resource ID only selects a target within that scope. Bind tenant and owner predicates in the SQL query itself instead of fetching a global row and hoping every caller remembers a second check.

**Transaction rule:** run creation commits the run, plan revision, task/dependency rows, configuration snapshot and initial events atomically. A task claim updates state and lease in one transaction. Completing an attempt, changing task/run status and appending transition events should share a transaction when they form one domain transition. Artifact bytes may live outside the database; use pending/uploaded/verified state so the DB never claims an artifact is complete before its hash and size are verified.

**Schema evolution:** add migrations tested against an empty DB and each supported prior schema. For local SQLite migration, back up first, assign existing data to one explicit personal tenant/principal, verify record counts/content hashes, and document rollback/recovery. Hosted PostgreSQL migrations should use expand/backfill/contract for large tables and never expose rows with partially populated owner columns.

### 5. Identity, authentication and authorization

The current loopback bind/origin controls are exposure and browser-CSRF mitigations; they are not authentication. Do not enable LAN, reverse-proxy, tunnel or public access while Gate 2 remains open.

For the first shared-deployment path, prefer integration with a maintained OpenID Connect identity provider rather than inventing a full identity provider in the application. Use standards-based authorization code flows and PKCE for public/native clients, exact redirect URIs, short-lived access credentials and secure refresh/session handling. If self-hosted local accounts are later required, define password hashing, MFA, account recovery, rate limits, session revocation and anti-enumeration requirements explicitly rather than implementing ad hoc login routes.

For browser sessions, use server-validated opaque sessions in secure HttpOnly cookies, an explicit SameSite policy, CSRF controls for state-changing requests, exact origin validation and rotation/revocation semantics. For native CLI clients, use a secure local identity/token store and an appropriate interactive authorization flow; do not place long-lived tokens in command lines, URLs, config files under a repository, debug logs or IPC output.

Every request must resolve a verified principal. Authorization then checks both the action and the target resource. At minimum, policy decisions consider tenant membership, workspace grant, resource ownership, role, operation, tool risk, profile capability and current policy version. Read/list/search/download/export/subscribe/replay/modify/delete/cancel/resume are separate operations to authorize. The server must derive tenant identity from trusted session/principal context and reject user-supplied tenant overrides.

Background tasks must store the initiating principal and tenant, then revalidate resource ownership and revocation-sensitive grants when claiming or resuming work. API-only authorization is insufficient because a worker, delayed message, artifact download or replay path can otherwise bypass request-time checks.

Personal mode creates an explicit local principal and personal tenant during bootstrap and passes through the same domain authorization services as shared mode. Avoid a hidden “loopback means trusted administrator” exception. Local CLI bootstrap is a trusted device action with documented constraints, not an implicit multi-user policy.

### 6. Tool safety and permission model

Tool permission is a server-side runtime decision, not a prompt convention.

- Assign every tool a stable ID, argument/result schema, risk category, side-effect declaration, resource scope and default grant.
- Compute effective permission on every invocation from the verified actor, tenant/workspace, run, agent profile grants, tool metadata and current policy.
- Deny by default on missing context, malformed arguments, unavailable policy or unknown tool IDs.
- Keep user-defined agent profiles declarative. A profile may request a capability but cannot grant it, select another tenant's secret, change the authenticated actor or switch to an unauthorized workspace.
- Require approval only for policy-defined high-impact actions. Routine work within the explicit grant may proceed autonomously. Persist approval scope and expiry, and ensure an approval is not replayable for a different action or target.
- Run shell and other risky tools with a minimal environment, controlled working directory, process timeout, output cap, cancellation/termination policy and configurable network access. Prefer argv-based execution over an interpolated shell string.
- Use filesystem allowlists and canonical containment checks, and re-check after resolving symlinks. Protect system paths, secrets, credentials, Git internals and files outside an authorized workspace.
- Treat browser/web tools as SSRF-capable: validate schemes, redirects, resolved addresses, private/link-local destinations and allowed network scopes; apply response-size/time limits and content sanitization.
- MCP tools enter through the same validation and authorization gateway. Transport-level MCP auth is not the same as NexusAgent tenant authorization; tool server identity, credentials and grants must remain explicit.
- Redact secrets and sensitive payloads before logging or sending tool results to sibling agents. Store bounded audit metadata by default, not unlimited prompts/credentials/output blobs.
- Apply per-tool CPU/time/memory/output limits and global/per-tenant concurrency quotas. A crashed or hung tool must not retain a run slot forever.

### 7. Orchestration and agent runtime

The existing planner/team runtime is the starting point, not a justification for a full rewrite. Preserve the current role generation, dependency-aware scheduling, peer messaging, provider routing, research modes and quality gates, while extracting state from globals and direct SQLite operations into well-defined services.

**Planner contract:** input is a validated goal plus policy/profile/workflow context; output is a typed plan with stable task IDs, dependencies, required capabilities, completion criteria, verifier requirements and budget estimate. Parse model output into a schema, validate it, and record the chosen plan revision. If validation fails, ask for a bounded repair or fail explicitly.

**Agent profile contract:** a profile defines role, mission, system instructions, permitted tool categories, write intent, model role/provider preference, dependency constraints and review responsibility. Validate identifiers, lengths, scopes and unknown fields before saving. Generated profiles pass the same validator as user-authored profiles and are stored without credential material.

**Worker contract:** each task executes with a fresh context containing task/run IDs, a scoped memory view, the task's data access rights, tool handles, provider selection, budget counter, event sink and cancellation token. Context objects are immutable unless the field is explicitly task-local mutable state. Avoid process-global active session IDs, active principal, provider selection or workspace path in shared multi-user workers.

**Scheduling:** validate the full graph before scheduling; detect cycles and missing prerequisites. A failed dependency yields an explicit blocked/failed downstream state, not a hung ready queue. Record attempt numbers, retry classification, backoff, lease, deadline and last error. Retry only transient failures within bounds. A worker lease expires safely after process loss, but reconciliation must avoid executing the same side-effecting operation twice; use idempotency and tool-specific recovery where possible. The current local starting point uses Python worker threads; keep the pool bounded and preserve synchronous provider/tool compatibility while the lifecycle is extracted. For the first hosted worker dispatcher, a PostgreSQL-backed job/lease table claimed in transactions (for example, using row locks with skip-locked semantics) is sufficient; do not add a broker as another source of truth at the start. Add Redis or a dedicated queue only when measured throughput, fan-out or availability requirements justify it. Persist task state and event history in the database regardless of the queue chosen.

**Lifecycle:** define one canonical status enum for API, database and all clients. At minimum it needs planned/queued, ready, running, waiting-for-approval or external input, blocked, completed, needs-review, failed and cancelled. Do not infer status from a UI spinner or thread existence. State transitions are validated centrally and recorded as events.

**Cancellation and recovery:** persist the cancel request; notify active workers; cancel cancellable async operations; terminate owned subprocesses after a grace period; record which operations may have side effects. On process restart, recover expired leases, inspect unfinished attempts, persist interrupted outcomes and resume only work proven safe to resume. The native/web clients must not be the authority for whether a run exists or is complete.

**Research:** maintain source policy modes user_only, hybrid and autonomous; collection policies single, timed, until_saturation and continuous; and depth policies from surface through maximal. Enforce source/tool availability before execution. Timed collection has a hard deadline. Until-saturation uses measurable marginal novelty/yield plus a hard cap. Continuous work requires cancellation, budget and retention policy. Persist source snapshots and exact quoted evidence so deterministic verifiers can check the source, not trust an LLM's claim that verification occurred.

### 8. API, events and client compatibility

Use FastAPI and Pydantic as the current API implementation. The API contract must be versioned and language-neutral. Establish a versioned route namespace for new contracts, migrate old endpoints through compatibility adapters and remove old routes only under documented deprecation rules. Avoid breaking the currently used local GUI and CLI while the contracts are being formalized.

Use one authoritative schema source. Pydantic models can define request/response structures initially; OpenAPI is then generated and used to generate TypeScript client types. The web UI must not hand-maintain another copy of the same domain types. Runtime validation remains mandatory because TypeScript's compile-time types do not validate untrusted JSON arriving over HTTP or WebSocket.

Mutating requests should support idempotency for run creation, tool action submission and other operations where retries can duplicate side effects. Use resource revisions or conditional updates where concurrent controls could conflict. Return stable error codes and non-sensitive details rather than leaking stack traces, file paths, database errors or credential metadata.

**Event envelope requirements:** every event has schema version, event ID, per-run sequence, event type, occurrence time, run/task/resource references, and a validated payload. The persisted event is authoritative; the stream is a delivery mechanism. Clients reconnect with a last-seen sequence/event ID and recover gaps from the event store or a state snapshot. Duplicates are permitted at-least-once delivery and clients deduplicate using event IDs; event ordering must be stable within a run. Never send secret values in event payloads.

For browser clients, enforce the authenticated session, origin/CSRF policy and resource ownership before upgrading/subscribing to a WebSocket. An arbitrary session or run ID in a URL does not establish access. For native clients, define reconnection, backoff, heartbeat, message size, protocol version and graceful shutdown behavior.

For existing Rust/Python stdio IPC, keep newline-delimited JSON/JSON-RPC only as a local process protocol with explicit method schemas, request IDs, cancellation, bounded message sizes and stdout reserved for protocol frames. Keep diagnostics on stderr. Do not create two competing APIs (one REST and one ACP) with different business semantics.

### 9. Web UI implementation

The current static HTML/CSS/JavaScript pages are a useful migration baseline and must remain functional during the transition. Do not perform a simultaneous big-bang rewrite.

Recommended progression:
1. Define the API and event envelopes first, including status/error semantics and pagination.
2. Introduce the TypeScript build and strict compiler settings alongside the current frontend assets.
3. Migrate one low-risk screen first, such as provider/model catalog or agent profile inspection; verify packaged assets and local installation still work.
4. Migrate configuration and scoped-memory pages using generated API types and server validation.
5. Migrate the team/workflow console: DAG view, agent roster, timeline, messages, tool invocations, verifier decisions, budgets, approval prompts and output/artifact viewer.
6. Add reconnect/replay and empty/error/loading states; do not assume the WebSocket never disconnects.
7. Migrate session/chat and security-sensitive provider credential management only after API auth/session contracts are ready.
8. Remove the legacy page only when equivalent acceptance tests pass and release packaging includes the compiled asset set.

Build a consistent component library with design tokens for color, typography, spacing, status, motion and contrast. Prioritize keyboard navigation, screen-reader semantics, reduced-motion settings, visible approval state, high-density but readable activity timelines and responsive layouts. The UI may visualize policy and collect user choices, but the backend must validate those choices. Keep secrets masked, never include them in browser storage/localStorage, and never treat hidden controls as authorization.

### 10. Rust client implementation

Keep the Python backend authoritative. Use the existing Rust workspace for the terminal UX and eframe desktop client. First document and test the current protocol; do not assume a proposed protocol method exists until it is visible in the code and covered by tests.

**Concrete native integration gaps found in the live source (2026-10-13):**

- `pyproject.toml` registers the Python CLI as `nexus = nexus_agent.__main__:main`, and `nexus-rs/Cargo.toml` also names its Rust binary `nexus`. These are mutually conflicting installers if shipped into the same PATH. Keep the Python CLI as canonical during parity work and expose the Rust client under a distinct development/preview name (for example `nexus-rs`). Change the stable `nexus` entrypoint only after the Rust command set is demonstrably at parity, packaging/upgrade/uninstall tests pass, and a compatibility route to the Python CLI is documented.
- The Rust ACP request builder exposes a `command` method, but the current `src/nexus_agent/mcp/acp_server.py` dispatcher handles `prompt`, `init`, `get_status`, memory methods and `stop` and has no matching `command` branch in the inspected implementation. This is protocol drift: either implement the method with a defined request schema and authorization boundary or remove it from the Rust client contract until supported. Do not silently turn a missing method into an interactive-only workaround.
- The Python ACP server dispatches incoming lines into concurrent tasks and writes notifications/responses to shared stdout. The current design must be qualified for frame interleaving, request correlation, prompt serialization, bounded buffering and shutdown. A run's model/tool context should not be used by overlapping prompt calls unless the runtime explicitly supports that concurrency. Add a single protocol-writer/serialization boundary and explicit per-request lifecycle rather than allowing arbitrary task code to write protocol frames concurrently.
- The ACP reader uses an unbounded Tokio channel for events, and the Python line reader does not establish a clearly shared message-size/backpressure contract. Add bounded line/frame length, bounded event buffering, an overload policy, process-exit signaling and tests proving slow consumers cannot cause unbounded memory growth.
- The native backend startup path initializes a SessionManager in `_init_agent` without retaining the manager reference in the shown implementation. Verify its lifetime and shutdown/close behavior with a startup/resume/message test; if it is not intentionally held by the agent/runtime, retain it in an explicit backend runtime object and close it deterministically.
- The Rust client currently has formatting/compilation CI but needs `cargo test` coverage for protocol serialization/parsing, malformed frames, request/response ID correlation, method coverage, backpressure, cancellation, child-process failure and graceful shutdown. A successful `cargo check` alone cannot prove the protocol is functional.



The Rust terminal client should own terminal lifecycle, rendering, keyboard input, input history, client-side navigation, graceful exit and backend process health display. It should send commands to the same run API/IPC service used by the web client, consume stable events and request snapshots when it detects a gap. It must not own run/task persistence or independently schedule agents.

The desktop client should own window layout, navigation, accessibility, notifications and client-side caches. It must use the shared authentication model and API contracts, keep session tokens in an appropriate OS-protected store, validate server messages and handle expiry/revocation. It should not connect directly to the database or share the CLI's in-process scheduler.

Before investing in deeper Rust work, add actual Rust unit/integration tests to CI. The live CI workflow currently validates Rust formatting and compilation; formatting/compilation alone do not qualify runtime behavior. Add tests for protocol framing, malformed messages, backend crash/restart, cancellation, timeouts, UTF-8/large event streams and client reconnection.

### 11. Observability, operations and reliability

Use structured logs and stable correlation identifiers for request, run, task, tool invocation and provider request. Redact provider secrets, authorization tokens and sensitive prompt/tool payloads. Record actor, tenant, action, target, outcome and policy revision for security-significant actions. Keep audit events separately protected from ordinary application logs.

Define metrics for queue depth, active runs, ready/blocked tasks, worker lease expiry, provider latency/error/rate-limit, token and cost consumption, tool failure/timeout, cancellation latency, event delivery lag, artifact volume and tenant quota denials. Instrument traces across API → run service → worker → provider/tool. OpenTelemetry is the recommended neutral instrumentation interface; the chosen exporter/backend may differ by deployment.

Readiness/liveness probes must distinguish process health from ability to accept new runs and ability to reach configured dependencies. Provide graceful shutdown: stop accepting new runs, persist state, signal cancellation or checkpoint workers, wait a bounded grace period and release leases. Define backup, restore, retention, secret rotation, deletion and disaster-recovery procedures before production release.

### 12. Test and CI qualification strategy

The current workflow is useful but does not yet fully prove the target design. It runs a cross-platform Python test matrix, Ruff, a strict MyPy subset, Rust format/check, synchronized version checks and security/audit jobs. The web frontend has no TypeScript build/test gate yet, and Rust compilation is not a substitute for Rust tests.

Required layers:

- **Unit:** schemas, status transitions, policy decisions, provider normalization, retry classification, ID parsing, artifact naming/containment, memory scope routing and source-policy enforcement.
- **Property/fuzz:** path and URL normalization, event parsing, malformed provider output, graph cycle detection, schema limits and protocol frame boundaries.
- **Repository contract tests:** the same ownership, transaction, migration and query behavior against local SQLite and shared PostgreSQL adapters.
- **API integration:** unauthenticated, expired, revoked, wrong-tenant and wrong-workspace requests; all CRUD/list/export/download/stream/cancel/resume endpoints; idempotent retries; CSRF/origin; error redaction.
- **Tenant negative tests:** User A cannot read, mutate, resume, cancel, subscribe to or export User B's runs, tasks, messages, memory, source snapshots, artifacts, agent profiles, audit logs or credentials by guessing IDs, switching request fields or racing membership revocation.
- **Orchestration integration:** dependency DAG, parallel waves, worker crash, hung tool, retry bounds, cancel/pause/resume, lease expiry, duplicate delivery, partial completion, budget exhaustion and recovery after restart.
- **Research quality:** every cited claim ties to a stored source/quote, rejected evidence is not synthesized as verified, contradiction/verification gates fail closed, source policy is enforced, and all stopping modes obey time/budget ceilings.
- **Tool security:** traversal and symlink escapes, disallowed network destinations/redirects, environment leakage, shell injection, oversized output, timeout, process cleanup and permission changes between planning and execution.
- **Frontend:** strict TypeScript compilation, component/unit tests, browser-level flows for create/run/control/reconnect/approval/artifact viewing, accessibility checks and responsive smoke tests.
- **Rust clients:** unit/integration tests plus cross-platform compilation/packaging, protocol tests, crash/reconnect and secret-storage behavior.
- **Performance/load:** benchmark rather than guess startup, first event/token, scheduler throughput, DB contention, memory growth, event lag and isolation under concurrent tenants. Publish workload and machine details with results.

A required workflow must run against the exact proposed merge head. Queued, skipped, cancelled or stale-head checks are not passes. Keep dependency/security gates and version-contract validation in the required merge gate, and qualify releases from saved test evidence.

### 13. Incremental delivery plan mapped to the authoritative roadmap gates

Use the seven sequential gates in docs/ROADMAP.md as the only release qualification sequence. The substeps below expand their implementation detail; they are not a competing roadmap or a claim that any gate has passed.

**Gate 1 — Repository and governance baseline**
- Keep master as the effective integration target until the default-branch migration to main is verified. Use ordinary, CI-gated, history-preserving merges; never force-push or rewrite history.
- Inspect current code, docs, tests, CI and live branch settings. Distinguish proven functionality from documented targets.
- Extend qualification so the exact merge head runs Python tests, lint/format, typed checks, Rust tests/builds, version checks and Security. A workflow that is queued, skipped, cancelled or tied to a previous head is not a pass.
- Exit evidence: one verified integration path, reproducible checks and administrator-confirmed branch settings.

**Gate 2 — Multi-user identity and isolation**
- Define principal, tenant, membership, workspace grants and session/revocation semantics in accordance with docs/STORAGE_AND_GOVERNANCE.md. Integrate a maintained OIDC provider for hosted identity rather than building an ad hoc identity provider.
- Replace connection-peer checks as the authorization concept with verified identity and resource-policy checks. Keep the non-loopback bind guard until the tests pass.
- Introduce ownership metadata and scoped repository methods. Test every operation category across API, worker, event, memory, artifact and credential access.
- Eliminate unsafe implicit local trust and the global active principal/workspace/session model. Personal mode must also create and enforce an explicit local principal.
- Exit evidence: negative cross-tenant tests pass for guessed IDs, forged tenant selectors, revoked sessions/memberships, background jobs, subscriptions, artifact downloads and provider secret references.

**Gate 3 — Shared runtime and contracts**
- Extract request handling from domain behavior, beginning with run/session lifecycle and repository access. Do not move everything to new packages at once.
- Define a single API contract with validated Pydantic models and generated OpenAPI; version new routes and maintain compatibility adapters for existing local clients.
- Define durable event envelopes, status/error enums, idempotent mutation behavior, reconnect/replay and protocol-version negotiation.
- Exit evidence: web, Rust CLI/TUI and desktop observe the same run states, errors, results and access rules from the same backend contracts.

**Gate 4 — Agents, tools and orchestration**
- Preserve the current planner/team behavior while validating plans as typed DAGs. Fail missing prerequisites/cycles explicitly; bound planning, agent count, concurrency, tool calls, retries, time and cost.
- Build task-scoped worker contexts, worker leases, cancellation propagation and deterministic terminal states. Make retryable failures explicit and account for side effects before retry.
- Use one policy gateway for file, shell, Git, browser/web, research, memory and MCP tools. Re-evaluate permission at each invocation.
- Exit evidence: integration tests cover normal completion, dependency failure, policy denial, human approval, provider/tool timeout, worker crash, cancel/pause/resume and budget exhaustion without deadlocks or unbounded retries.

**Gate 5 — Research, memory and persistence**
- Retain local SQLite for supported offline/personal operation. Add PostgreSQL repositories and migrations for hosted multi-user operation; shared deployment must not rely on a single process-global session manager or workspace database as its ownership boundary.
- Add artifact-store adapters, owner metadata, retention/deletion and migrations without breaking the current local storage layout. Keep credentials in a dedicated secret store.
- Preserve user_only/hybrid/autonomous source modes and single/timed/until_saturation/continuous collection modes as enforced runtime policy. Depth must change actual budgets, source breadth and verification rules.
- Exit evidence: storage/recovery/migration and memory-scope tests pass; source/claim evidence can be traced to captured snapshots; all collection modes respect caps and deadlines.

**Gate 6 — Client and end-to-end qualification**
- Modernize the current static HTML/CSS/JavaScript UI incrementally to TypeScript + React + Vite after the API/event contracts stabilize. Start with one low-risk screen and maintain functional static packaging until each replacement qualifies.
- Generate browser-client types from OpenAPI, add strict TypeScript compilation and browser tests, and implement timeline reconnection/replay, error/loading/empty states, accessible navigation and explicit approval controls.
- Keep the Rust CLI/TUI and eframe desktop as presentation clients. Add Rust tests for protocol framing, invalid messages, reconnection, backend failure, cancellation and large/Unicode event streams.
- Exit evidence: acceptance scenarios for create-run, progress/event display, tool/approval state, artifact viewing, cancellation, reconnect and session expiry pass across clients.

**Gate 7 — Release and operational qualification**
- Add structured logs, trace correlation, metrics, redaction, readiness/liveness, graceful shutdown, backup/restore, retention, credential rotation and quota dashboards.
- Run the full supported Python/OS matrix, static analysis, OpenAPI/TypeScript build/tests, Rust fmt/test/check/build, dependency/security audits and version contract on the exact release candidate.
- Publish only from the verified canonical branch with an immutable tag and verified provenance. Resolve all security blockers and document remaining limitations.
- Exit evidence: exact-commit workflows pass, recovery procedures are exercised, the version/changelog is correct and repository settings are confirmed by an administrator.

### 14. Performance and optimization rules

Do not publish guessed performance targets as current results. Establish benchmark baselines with reproducible task inputs, provider/model, concurrency, host platform, output size and warm/cold state. Measure p50/p95/p99 latency, throughput, memory, queue wait, error rates and cost.

Optimize in this order:
1. correctness, isolation and observability;
2. identify measured bottlenecks;
3. reduce duplicate provider calls and unnecessary serialized planning;
4. introduce bounded concurrency and appropriate I/O overlap;
5. improve database indexes/transactions and event batching;
6. optimize artifact traversal and large payload handling;
7. only then evaluate alternate runtimes or Rust/native acceleration.

Do not trade away permission checks, ownership predicates, deterministic evidence or event durability to improve a benchmark. Every performance change must include a compatibility test demonstrating that visible result sets and security boundaries remain unchanged.

### 15. Architecture decisions to reject

- A Rust rewrite of the agent core because Rust is present in the repository.
- A second TypeScript backend while Python continues to own tools, providers and runs.
- Multi-user exposure protected only by loopback, IP allowlists, CORS or Origin checks.
- A tenant ID chosen by the browser, a random-looking resource ID treated as authorization, or authorization performed only at the route and skipped by workers/repositories.
- Separate orchestration implementations in GUI, CLI/TUI and desktop.
- A planner loop with no hard budget or deterministic terminal state.
- In-memory events or thread maps as the sole source of truth for durable runs.
- Unlimited tool output, shell execution, retries, browser navigation or continuous research.
- Credentials stored in plain project config, agent profiles, prompts, logs, WebSocket events or exported artifacts.
- A framework/microservice/queue migration without a measurable need and an incremental compatibility plan.
- Release qualification based on a single Linux run, a green check on an old head, a skipped job or untested documentation claims.

### 16. References for implementation details

- Python asynchronous I/O: https://docs.python.org/3/library/asyncio.html
- TypeScript language/type system: https://www.typescriptlang.org/docs/handbook/intro.html
- React with TypeScript: https://react.dev/learn/typescript
- Rust ownership and resource safety: https://doc.rust-lang.org/stable/book/ch04-00-understanding-ownership.html
- PostgreSQL row-level security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- OAuth 2.0 security best current practice: https://www.rfc-editor.org/rfc/rfc9700.html
- Model Context Protocol authorization: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- OpenTelemetry: https://opentelemetry.io/docs/

