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


## Runtime hardening

Worker tool authorization is resolved against the worker-local tool graph, so dynamically injected tools such as research evidence operations are evaluated using their actual permission metadata rather than the parent runtime catalog.

Research source policy is enforced at tool exposure time:

- `user_only` exposes configured-source retrieval and removes arbitrary web discovery/source-fetch tools.
- `hybrid` uses configured sources first and permits autonomous expansion.
- `autonomous` permits general source discovery.

The evidence ledger records source text fetched by the source tool itself; worker-supplied source snapshots are not treated as authoritative evidence.

Dependency scheduling validates all declared dependencies before constructing a ready wave. Unknown dependencies fail closed and cannot execute accidentally. Provider routing also fails over when a configured primary provider cannot be initialized.

Artifact-serving API routes resolve team artifact roots beneath the canonical runtime artifact directory and reject traversal outside that boundary.


Autonomous source capture also rejects credential-bearing URLs and common loopback, localhost, link-local, private, reserved and multicast IP targets to prevent research tools from becoming an SSRF primitive. Explicitly configured `user_only` sources remain under the user's explicit source policy.


## API data boundary

Team control and persisted team-data endpoints are loopback-only. Remote clients are rejected from team history, status, messages, events, reports, artifacts, audit records, research exports and live team streams. This prevents the multi-agent runtime from becoming an unauthenticated remote data-exfiltration surface when the web service is exposed beyond localhost.


## Authoritative platform requirements (2026-10-13)

### General-purpose scope and deployment

The platform supports coding, research, analysis, planning, automation, document/artifact production and other task types through one shared runtime. Research is a first-class subsystem, not the product boundary. Both local/personal and authenticated multi-user deployment are required from the initial architecture.

### User-defined and generated agents

Users may author, configure, inspect, edit, persist, reuse and select agents. A user may also ask NexusAgent to generate a reusable profile from a natural-language role requirement. The planner may generate missing specialists when a task has a real capability gap. Generated profiles must pass schema and policy validation; generation must not request, expose or embed credentials.

A profile describes role and requested capabilities. It does not grant permissions. Effective permissions are resolved by the runtime from user/tenant policy, workspace scope, configured grants and the current task. Agents operate autonomously within those permissions; approval is required only where the configured policy calls for it.

### Bounded execution

Every run must have configurable limits for total agents, generation depth, concurrency, wall-clock time, token/cost budget, tool calls, retries and artifact volume. Dependency cycles and unknown dependencies fail explicitly. A failed task must not trigger unbounded replanning. Cancellation must propagate to workers and child processes where supported.

### Canonical task lifecycle

Use an explicit, documented lifecycle covering planned, ready, running, waiting, blocked, failed, cancelled, completed and verification outcomes. The precise enum may be refined by implementation, but API, persisted state and clients must share one contract. Events must have stable IDs and identify the run, task, actor, tenant/workspace, timestamp and outcome.

### Multi-user isolation

All team, worker, message, artifact, event, session and memory access must enforce ownership on the server. Shared SQLite/workspace storage is suitable only where its locking, ownership and deployment constraints are satisfied; multi-user deployment requires a storage design that supports concurrent access, migrations, durable transactions and tenant isolation. Never assume that a loopback origin alone establishes user identity.

### Research behavior

Preserve these modes as behavioral contracts:
- Source: `user_only`, `hybrid`, `autonomous`.
- Collection: `single`, `timed`, `until_saturation`, `continuous`.
- Depth: configurable from surface-level to extreme thoroughness, with depth affecting actual source breadth, verification, contradiction analysis and stopping rules.
- Sources: user-supplied documents and authorized local directories; web/browser sources only as permitted by mode and policy.
- Evidence: retain source provenance and snapshots where appropriate; distinguish source content, extracted claims, agent interpretations and verified conclusions.

The UI must show real runtime events, not simulated activity. Users should be able to inspect role generation, task dependencies, peer messages, tool calls, transferred artifacts, retries, verification and final results.
