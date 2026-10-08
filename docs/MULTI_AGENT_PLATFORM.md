# NexusAgent Multi-Agent Platform

NexusAgent is a local-first agent runtime and workbench. A task can run as one agent or as a dynamically assembled team of specialized peer workers.

## Operating modes

- auto: infer the appropriate operating mode from the task
- code: repository/software engineering
- research: source collection and evidence-oriented investigation
- review: independent/adversarial review
- analysis: systems/domain analysis
- plan: planning and architecture
- automation: workflow/automation engineering

## Team execution

The team architect converts the goal into typed professional profiles:

- profession and mission
- role-specific instructions
- tool categories
- write permission
- reviewer responsibility
- model role
- dependencies

Workers run concurrently up to the configured parallelism. Each worker is a real AgentLoop instance with its own context.

Workers share a persistent SQLite blackboard at:

<workspace>/.nexus-agent/runtime/teams.db

The blackboard stores:

- team metadata/configuration
- worker profiles and lifecycle
- direct/broadcast messages
- worker events and tool activity
- completion/failure records
- final synthesis

Every worker receives two team tools:

- team_send_message
- team_read_messages

This creates a structured team communication channel without forcing uncontrolled conversational cross-talk.

## Permissions

Team execution defaults to safe behavior. Read/search/web/git inspection tools can run through the normal permission system; write/edit/shell/commit-like operations remain subject to the configured permission policy.

The CLI exposes --yes for deliberate non-interactive runs that should automatically approve tool calls.

Teams also support persisted pause/resume/stop requests, dependency-aware scheduling, per-agent provider/model routing, chat/file/both output modes, and deterministic research quality gates.

## CLI

After pip install -e .:

nexus-team run "Inspect this repository, implement the requested feature, test it, and independently review the result." --mode code --max-agents 6 --parallelism 4

Inspect a persisted team:

nexus-team show <team-id>

## Web console

The existing NexusAgent web application now exposes:

/team.html

The console shows:

- task and team controls
- generated professions
- agent lifecycle/state
- live counters
- peer messages
- execution events
- final synthesis

It shares the same provider/workspace state as the primary NexusAgent dashboard.

## Native client

nexus-rs/ remains the native Rust client and TUI. It is the native surface for the same agent runtime. The team runtime is implemented in the shared Python core and is available through the web and team CLI; native team controls can use the same local service/IPC boundary without duplicating orchestration logic.

## Design principle

NexusAgent deliberately keeps orchestration, permissions, tools, providers and persistence in the shared core while treating web, CLI/TUI and native clients as presentation/control surfaces.

That means a team started by the web client is the same type of persisted team that can be inspected by the CLI, and the native client does not need a second implementation of planning, provider routing, tool execution or team messaging.

## Agent definitions

Agent profiles are Markdown files with YAML front matter and explicit scope:

- built-in
- global
- user
- project
- workspace

Use `nexus agent init` to author a profile, `nexus agent generate` to have an LLM design profiles from a requirement, and `nexus agent list/show/validate` to inspect them. A team may pin saved profiles while still asking the planner to generate additional specialists.

## Tooling

Team workers share the platform tool catalog, filtered by role:

- filesystem read/write/delete/move/restore
- shell
- code editing and batch editing
- Git/CI/PR tooling
- browser + web search/fetch
- structured data parsing
- repository/code intelligence
- LSP
- scoped memory
- MCP tools
- research evidence/source tools
- reusable skills

Side-effecting tools remain permission-gated.

## Provider routing

Provider credentials are stored separately from project configuration. Agents may specify a provider, model, fallback chain, and model role. The provider catalog supports common hosted/custom OpenAI-compatible providers, local runtimes, and NVIDIA NIM. Models.dev metadata can be cached for discovery without storing credentials.

## Research evidence gate

Research-mode teams persist source snapshots, exact quotations, claims and verifier records in `<workspace>/.nexus-agent/runtime/research.db`. The selected research depth determines the required independent-verification threshold. Rejected candidate claims do not block completion, but unresolved claims and an evidence gate failure move the team to `needs_review`.

## Storage

Durable workspace runtime data is isolated under:

`.nexus-agent/runtime/`

This contains team/research databases, activity/audit records, generated artifacts, reversible-delete trash and other run state. User-wide credentials and memory live outside the repository workspace under the platform data directory.

## Client parity

The authoritative orchestration runtime is shared. Web, CLI/TUI and native clients are presentation/control surfaces over the same team state, tools, permissions and provider routing. The native desktop client uses the local web runtime rather than duplicating the orchestration implementation.
