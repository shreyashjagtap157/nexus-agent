# NexusAgent — Local Multi-Agent Workbench Completion Goal

You are the implementation team working in the user's existing Git repository:

`https://github.com/shreyashjagtap157/nexus-agent`

The product name is **NexusAgent**. The final product is a local-first, provider-agnostic agent runtime and workbench for software engineering, repository operations, research, analysis, writing, automation and other tool-driven tasks. It must support the familiar workflow of single-agent coding tools while adding dynamically assembled, concurrently executing, communicative multi-agent teams. Research is one mode, not the product boundary.

## Mandatory start-of-task repository protocol

1. Inspect the actual repository and remote state before editing. Run `git status --short --branch`, `git remote -v`, `git fetch --prune origin`, inspect `origin/main` and `origin/master`, inspect recent commits, open pull requests, branch protection/rules, CI workflows, package metadata, docs, and tests. The GitHub repository has both `main` and `master`; repository metadata has historically still listed `master` as its default even though the multi-agent integration PR was merged into `main`. Establish which branch is canonical/protected from live evidence. Use `main` for implementation if it is the current governed integration branch; do not rename the default branch or rewrite history silently.
2. Preserve local user work. If the working tree is dirty, inspect and preserve it; do not run destructive reset/clean commands over unreviewed user changes. Never force-push, rewrite published history, or discard changes just to make tests pass.
3. Work in the existing repository, not a replacement scaffold. Read README, docs, specifications, architecture notes, pyproject/Cargo manifests, CI workflows, providers, tools, memory, MCP, permission, server, CLI/TUI, frontend, and native client code before designing changes. Treat code, tests, and live GitHub state as evidence; do not treat previous agent summaries as proof.
4. Create a repo-grounded plan and update it as dependencies are discovered. Work through all feasible milestones in this run rather than stopping at a plan. Update docs and architectural decisions when behavior/design changes. Make cohesive commits on the agreed integration branch and push without rewriting history when tests and branch governance permit. Do not claim a push, merge, successful live inference or test run unless the corresponding remote/API/output evidence exists.

## Product architecture and completion target

Build one authoritative local control plane and runtime, with web, CLI, interactive TUI, native desktop and programmatic API clients sharing the same session store, agent runtime, tools, permissions, provider registry, message bus, event stream and workspace model. Avoid implementing duplicate orchestration logic in each client.

### 1. Clients and server

- Web app: a refined, responsive, information-dense operations workbench with task composer, sessions/workspaces, agent/team topology, task graph, message flow, model/provider activity, permissions/approval inbox, terminal/processes, files/diffs, tests, research evidence, artifacts, memory, MCP, configuration, audit log, and runtime health.
- CLI: interactive and non-interactive commands, streaming/JSONL output, session create/list/resume/fork, `run`, `team`, `agent`, `model`, `provider/auth`, `tool`, `mcp`, `memory`, `workspace`, `permissions`, `logs`, `doctor`, `test`, and artifact/report commands. Use discoverable `--help`, consistent exit codes, cancellation and machine-readable results.
- TUI: provide a real terminal-first team/session experience; do not make the TUI a nonfunctional decorative shell.
- Native desktop application: build on the existing Rust native client. Prefer the existing architecture if sound; otherwise use a maintained Rust desktop shell (for example Tauri) with a TypeScript frontend and the same local service. Share UI components with the web app where sensible. Document supported OSes and create actual build/package pipelines, not just a Cargo source folder.
- Local service/API: documented OpenAPI HTTP API plus streaming events (SSE or WebSocket where appropriate). Bind to loopback by default. Any optional LAN/remote access must be explicit and authenticated. Include health/readiness, session/team controls, events/messages, provider/model catalog, agent catalog, approvals, artifacts and workspace inspection APIs.

### 2. Core agent runtime and orchestration

Implement typed, persisted objects for sessions, tasks, dependencies, agent profiles/instances, teams, messages, tool calls, approvals, events, artifacts, model requests, memory references and final outputs. Use explicit lifecycle states and defined terminal conditions.

- Single-agent, pair, team, swarm and autonomous-team execution using the same runtime.
- Planner that classifies task intent, asks only necessary clarifying questions, decomposes goals into verifiable work items and dynamically generates professional roles with distinct missions and bounded permissions.
- User can create/edit/import/export/enable/disable/pin agent profiles manually, or ask an LLM to generate profiles from natural-language requirements. Generated profiles are validated and previewable before persistence. Support built-in, global, user, project and workspace scopes with documented precedence; session/team overrides must be explicit.
- Team members run concurrently where independent and wait for prerequisites where dependencies exist. Detect dependency cycles/unknown dependencies, cap fan-out and budgets, handle failure/timeout/cancellation, retry idempotently, and avoid deadlocks. Do not pretend workers are independent peers if all work is actually serial; expose their real state.
- Typed message bus with direct/broadcast messages, request/reply, handoff, review request, evidence, artifact, blocked/warning, approval and completion types. Persist sender/recipient, team/session/task, parent/causal message, timestamp and structured payload. Make communications inspectable and searchable. Use a shared blackboard/state store for durable findings and task handoffs.
- Shared workspace access with concurrency controls and clear ownership. Prevent competing writers from corrupting the same files. Use worktrees or isolated workspace snapshots when parallel changes conflict; integrate through patches/merges with explicit review.
- First-class pause/resume/stop/cancel/retry, progress, queue, deadlines, per-agent budgets and recoverability after a process restart. State what cannot be resumed safely.
- Final synthesizer must distinguish agreed findings, disagreement, missing work and failures. Independent reviewer/auditor must inspect actual artifacts, diffs and test outputs rather than trusting agent claims.

### 3. Tools and execution harness

Use a single versioned tool catalog available to individual agents according to capability and policy. Implement and test at least:

- Filesystem: bounded listing/search, read with line/range limits, create/write/edit/patch, move/rename, delete through recoverable trash by default, restore from trash, file diff, directory operations and artifact management. Every path must be safely confined to the approved workspace unless an explicit grant permits otherwise; defend against symlink/path traversal and `.git`/credential hazards.
- Process/shell: launch command, stream output, track PID/status, timeout, cancellation, exit code, working directory and resource limits; truncate/persist logs safely. Shell execution is approval-gated by default and must never silently auto-approve a destructive command.
- Git: inspect status/log/diff/blame, branch/worktree operations, commit, and push behind clear approval. Never force-push or rewrite history. Provide test/build/CI output as artifacts.
- Web/search/fetch/browser: configurable search providers; fetch pages and PDFs; browser automation when needed; preserve source URLs/retrieval timestamps/content hashes; enforce request limits and defend against prompt injection/untrusted page instructions.
- Structured data/documents: parse JSON/YAML/TOML/CSV/XML, PDF, Markdown and common office documents with size/time limits and clear parse errors.
- Code intelligence: language-server/LSP integrations, symbol/reference search, diagnostics, import/call graphs, formatters, linters and test runners when available.
- Delegation/review tools, TODO/task graph, codebase indexing/RAG and memory tools. Avoid recursive uncontrolled subagent spawning.
- MCP client integration with a documented protocol implementation, stdio and supported HTTP transport, tool/resource/prompt discovery, configurable server scopes, timeouts, reconnect/error behavior and explicit per-agent permissions. Treat MCP tool metadata/results as untrusted input. If serving MCP itself, document authentication and tool-exposure rules. Avoid claiming support for transports not implemented or tested.
- Tool schemas must accurately match required/optional parameters, validate arguments, bound outputs, emit lifecycle telemetry and return structured errors. No tool may claim success unless the underlying operation succeeded.

### 4. Security and permissions

Define a threat model and security architecture. Apply least privilege, default-deny where reasonable, role-based and per-task tool allow/ask/deny policies, auditable approval gates, safe subprocess handling, path confinement, secret redaction, prompt-injection boundaries, rate/budget limits, resource limits, error isolation and dependency/security scanning. Separate the user's workspace files from NexusAgent state. Do not call the system “military-grade” as a substitute for measurable guarantees: document threats, mitigations, tests and residual risks.

Destructive changes, command execution with side effects, dependency installation, credential access, repository mutation, Git push, network exposure and irreversible deletion require explicit policy/approval. Respect user approvals consistently across web, CLI, TUI and native surfaces.

### 5. Provider and model ecosystem

Build a provider/model system inspired by OpenCode's architecture patterns, without copying its implementation wholesale or hardcoding a short list as the entire ecosystem.

- Separate provider/model configuration from credentials/authentication.
- Support custom OpenAI-compatible `base_url` and model IDs as a first-class path, plus direct adapters for APIs whose protocol differs. Support local endpoints such as Ollama, LM Studio, llama.cpp/vLLM-compatible servers, NVIDIA NIM and common hosted providers through provider adapters or a maintained compatibility gateway/library when appropriate.
- Provide per-agent/per-role model selection, capabilities, context/output limits, tool-calling/vision/streaming flags, timeout, retry, ordered fallbacks and provider health. Record actual provider/model used per inference call. Do not assume every model supports the same features or parameter names.
- Use dynamic or regularly refreshed model metadata where feasible; model availability may change independently of code releases. Cache safely and surface stale catalog state.
- Provide login/list/logout/test provider workflows. Prefer the OS keychain/credential manager for secrets; support environment variables and a permission-restricted local fallback. Never return raw secrets from APIs, logs, errors, reports or telemetry. Add `.env.example` only; keep real credentials out of Git and all generated artifacts.
- Test auth, base URL, model IDs, malformed responses, timeouts, rate limits, `Retry-After`, fallback selection and request/response normalization. Live provider tests are opt-in and separate from deterministic CI; use disposable secrets and never include keys in output.

Inspect OpenCode's current provider/auth/model metadata implementation and docs as an architecture reference. Reuse official provider APIs/SDKs or compatible libraries where suitable, but obey licenses and do not copy source code without license review. Document supported adapters with evidence and tests rather than asserting “every provider” without coverage.

### 6. Memory, storage and file lifecycle

Implement and document these separate scopes: global installation defaults, user-wide, project, workspace, agent, team and session memory. Define precedence, isolation, sharing/visibility, retention, deletion and explicit promotion between scopes. Persistent facts must have provenance and be editable/forgettable. Never silently promote confidential workspace content to global/user memory. Provide memory inspection, search, stats, export and forget/clear controls.

Create a canonical storage layout and migration policy. Keep provider credentials/auth outside the repo; keep global/user config in platform-appropriate user data directories; keep project-specific profiles/settings in documented project locations; keep databases, checkpoints, caches, sessions, logs, event records, indexes and generated artifacts under the chosen runtime data root. Add a storage doctor and garbage-collection/retention controls. Do not commit runtime databases, user source corpora, secrets, logs or generated outputs.

Document file behavior: default write locations, workspace boundaries, overwrites/patch semantics, backups/recovery, naming, encoding, artifact metadata/checksums, retention, auditability and how users inspect/revert every modification. Use atomic writes for important settings/artifacts and schema-versioned migrations for durable stores.

### 7. Research and evidence mode

Keep research as a first-class workflow plugin, not the only engine. Retain and improve the independent Evidence Research Orchestrator concepts where useful:

- user-supplied URLs/files/directories/text and reusable source library;
- autonomous/hybrid/user-only discovery and configurable continuous/saturation/time/source budgets;
- the 21-level depth ladder from Glance through Maximal, with explicit operational policies rather than labels alone;
- source snapshots, canonical URLs, content hashes and independence/deduplication semantics;
- claim-level ledger with exact quotations, source-specific verification records, independent verification and explicit conflict adjudication;
- final writing constrained to accepted evidence and an auditor mapping final claims to evidence;
- formal review and proof obligations separated from machine-checked proofs. Only a real proof/model-check artifact produced by an actual prover may be called machine-proven.

Keep the independent repository `evidence-research-orchestrator` separate unless the user explicitly requests otherwise. Do not copy it wholesale into NexusAgent; port reusable behavior through modular interfaces and tests, preserving its own independent release history.

### 8. Observability and UI quality

Make logs and tracing exhaustive but manageable. Persist an event envelope containing event ID, run/session/team/agent/task IDs, parent/correlation IDs, timestamp, stage/type, duration, status, provider/model, token/cost fields when available, tool name, permission/approval decision, artifact references and structured payload. Redact secrets by default. Full prompt/response retention must be an explicit opt-in or clearly configurable because it can retain sensitive data.

The UI must show planned roles versus instantiated agents, real lifecycle state, dependencies/topology, direct/broadcast messages, tool inputs/outputs, approvals, data/source transfers, active processes, files changed, diffs, tests, provider request details, errors, retries, token/cost metrics when available, activity history and final artifacts. Provide search/filter, pagination/virtualization for long runs, per-agent inspection, event replay, export, correlation drill-down and accessible keyboard-first interactions. UI indicators must come from persisted runtime state, never fabricated animation or mock counters.

### 9. Versioning and release engineering

Use Semantic Versioning (`MAJOR.MINOR.PATCH`) for public releases, with pre-release/build metadata where appropriate. Keep one authoritative product version and define how Python package, Rust crate/native app, API and release tags remain aligned. During 0.x, breaking changes may increment MINOR according to the documented compatibility policy; do not invent revision-style versions unless the project explicitly documents a different scheme. Maintain a changelog, migration notes, release notes, upgrade path and reproducible release artifacts. Add automated checks that reject mismatched versions and tags.

Use conventional, descriptive commits; avoid unrelated changes. Maintain Git history. Establish branch protection/rules, required tests/reviews and status checks on the canonical integration branch where repository permissions permit. Never claim branch protection is active without checking GitHub's effective rules.

### 10. Quality gates and actual validation

Read and extend existing GitHub Actions instead of duplicating them blindly. Build a CI matrix for supported Python versions and Windows/Linux/macOS; Rust formatting, clippy and test/build checks; frontend type/lint/unit/build checks; package/install/CLI smoke tests; API and local-server E2E; migrations and concurrency; filesystem and permission security tests; tool contract tests; provider mock/contract tests; MCP transport and failure tests; restart/resume/stop/retry tests; audit/log redaction; artifact integrity; packaging and version consistency. Add supply-chain/dependency audit and secret scanning. Use deterministic local fake providers only for deterministic CI, clearly label them, and never let fake tests be reported as live-provider evidence.

For real provider tests, use an explicit environment variable/CI secret, small bounded prompt/budget, clear opt-in, strict timeouts, sanitized output and failure classification (DNS/network, auth, quota, request schema, provider service, application defect). Include a full manual validation checklist for web, CLI, TUI, native desktop packaging and real provider inference. Test actual outputs, not just import/syntax checks.

## Recommended implementation sequence

1. Audit the current remote repository, current merged code and CI; produce an evidence-based gap matrix and architecture decisions.
2. Stabilize core data contracts, schema migrations, runtime lifecycle, event/message bus, permission model and canonical storage layout.
3. Complete provider/auth/model routing and tool harness contracts; write unit and integration tests before expanding features.
4. Make configurable/generated agents first-class, with scope precedence and reusable profiles.
5. Finish concurrent dependency-aware team execution, inter-agent messaging, shared workspace conflict handling, lifecycle controls and crash/restart semantics.
6. Complete tool catalog/MCP integration and scoped memory.
7. Integrate research/evidence workflows as a modular mode with the standalone ERO remaining independent.
8. Bring API, CLI, TUI, web UI and native desktop clients to feature parity over the shared control plane; upgrade UX from real event/state models.
9. Add end-to-end regression/security/performance tests, OS/package matrices and live provider checks where network and credentials are available.
10. Reconcile SemVer/version sources, docs, release automation, repository rules and installation/upgrade stories.
11. Continue closing evidence-backed gaps until the acceptance matrix is satisfied; do not stop after a UI-only demonstration or a planning document.

## Acceptance criteria

- A clean checkout installs through documented native scripts without containers.
- A user can configure a custom OpenAI-compatible provider and safely test an inference; NVIDIA NIM/Nemotron configuration is documented and tested when network/key are available.
- A task can run as one agent or generate/reuse a team of distinct professionals; independent workers genuinely run concurrently and dependent tasks respect ordering.
- Agents can send/receive persistent messages and share durable artifacts without file corruption or role-ID collisions across runs.
- Tool permissions and approvals are consistent across every client; unsafe/destructive actions are not silently authorized.
- User-managed agent profiles can be created, edited, generated, validated, scoped, selected and deleted.
- MCP servers/tools are discoverable/configurable with honest support claims and per-agent permission enforcement.
- Global/user/project/workspace/agent/team/session memory is isolated and manageable.
- Research claims are linked to preserved sources and verifiable evidence; contradictions and formal proof status are honest.
- Web, CLI, TUI and native desktop surfaces use the same sessions, runtime, logs and artifacts.
- Activity is persistent, inspectable, searchable, exportable and secret-redacted by default; the UI reflects genuine event/state data.
- Clean CI passes all supported platform/build/test gates. Live inference is separately and truthfully reported.
- Version metadata, changelog, tags, package artifacts and docs agree; installation/upgrade/rollback procedures are documented.
- Final report lists changes, exact commits, tests actually executed, live provider outcomes, known limitations, and evidence for each acceptance item. No mock-only path is reported as production-complete.

Prioritize secure, testable completion and real integration over gratuitous complexity or claims such as “universal/military-grade.” Define measurable guarantees and record residual limitations. Continue development in coherent increments with docs, tests, telemetry and acceptance evidence for every major behavior.
