> **Authoritative product decision update — 2026-10-13:** NexusAgent must support local/personal and authenticated multi-user deployment from the initial architecture. Do not defer tenant-aware identity, authorization, storage, credential isolation, quotas, auditability or recovery design. Remote exposure remains gated on qualification of those controls. Agents operate autonomously within configured permissions; the runtime enforces those permissions. The language recommendation is requirements-first: Python core, TypeScript web UI, Rust native/system-sensitive components where justified. Work proceeds through sequential qualification gates, each supported by evidence tied to the exact candidate commit.
>
> **GitHub governance discrepancy:** GitHub currently reports `master` as the default branch; `main` also exists. The intended canonical branch and protection configuration must be reconciled as an explicit migration, not assumed from this document.

# NexusAgent Execution Roadmap

> **Current baseline:** 0.3.0-alpha.5
> **Status:** Active hardening and release qualification
> **Intended canonical integration branch:** `main` (live GitHub default is currently `master`; reconcile the migration before relying on branch policy)

This roadmap supersedes the original 0.2.x planning document. Historical implementation estimates from that document are no longer authoritative; the repository state, tests, CI workflows and current architecture documentation are authoritative.

## Current platform baseline

The unified NexusAgent platform currently includes:

- single-agent and multi-agent team execution using real `AgentLoop` workers
- professional agent generation and scoped saved-agent definitions
- dependency-aware team scheduling, persistent team history and lifecycle controls
- evidence-first research with source capture, claim verification, contradiction handling and deterministic quality gates
- worker-local tool authorization and fail-closed dependency handling
- provider/model routing with initialization failover and NVIDIA NIM/OpenAI-compatible support
- persistent workspace/team/research artifacts with path containment
- current documented limitation: sensitive team-control and team-data APIs are loopback-only; authenticated tenant-scoped access is a target requirement and must not be inferred from the local-only boundary
- guarded autonomous web fetching with private-target and redirect protection
- Python CLI/web surfaces plus native Rust CLI and desktop clients
- cross-platform CI, lint/type validation, native compilation, version contracts and security gates
- reproducible release validation and provenance-oriented packaging workflow

## Sequential qualification gates (authoritative)

Complete these gates in order. A gate is complete only when its acceptance criteria are demonstrated by tests, exact-commit workflow results, artifact inspection or verified repository settings. Historical status statements do not satisfy a gate.

### Gate 1 — Repository and governance baseline
- Reconcile default branch `master` versus intended canonical `main`; avoid PRs splitting across the two branches.
- Verify required CI/Security workflow triggers, check names, latest-head execution and repository protection settings.
- Inventory current code/spec/test coverage and distinguish verified implementation from target requirements.
- Exit: one authoritative integration branch, reproducible CI and a documented baseline of blockers.

### Gate 2 — Multi-user identity and isolation
- Define authentication, tenant/workspace membership, roles, session ownership and a local-mode bootstrap identity.
- Enforce authorization on APIs, background jobs, memory, provider secrets, artifacts, events, cancellation and resume.
- Add negative cross-tenant tests, per-tenant concurrency/resource budgets, safe audit events and recovery/migration tests.
- Exit: tenant isolation is proven by tests; remote/shared access remains disabled until this gate passes.

**Current implemented mitigation (2026-10-13):** GUI/API startup now rejects non-loopback bind addresses before initializing shared runtime state. This reduces accidental network exposure. Browser-originated API calls also require an exact loopback origin match, and WebSocket origin checks reject foreign origins; these are defense-in-depth/CSRF controls, not authentication or tenant authorization. Gate 2 remains open until identity, ownership-aware persistence, credential isolation and cross-tenant tests qualify.

### Gate 3 — Shared runtime and contracts
- Specify versioned task/session/API/event contracts shared by web, CLI/TUI and desktop clients.
- Prove durable task state, cancellation, reconnect/replay, error normalization and ownership enforcement.
- Exit: the same task semantics and results are observable through each supported client.

### Gate 4 — Agents, tools and orchestration
- Verify user-defined and generated agent profiles, schema/policy validation, bounded planning and dependency-aware scheduling.
- Verify tool schemas, permission enforcement, path/network controls, timeouts, retries and auditability.
- Exit: real multi-agent workflows complete with verified outputs, and unauthorized/failed/cancelled cases behave deterministically.

### Gate 5 — Research, memory and persistence
- Verify all source and collection modes, configurable depth, local sources, evidence provenance and measurable saturation/deadline behavior.
- Verify global, user, workspace, project and session boundaries plus concurrent writes, restart recovery and migrations.
- Exit: each advertised mode and scope has executable positive and negative tests.

### Gate 6 — Client and end-to-end qualification
- Demonstrate real tasks through web, CLI/TUI and native desktop, with live workflow events, messages, tool results and artifacts.
- Verify local and authenticated multi-user deployment profiles without duplicating domain logic in clients.
- Exit: end-to-end acceptance scenarios pass against the same candidate runtime and documented configuration.

### Gate 7 — Release and operational qualification
- Run full platform test, lint, type, native, security, dependency and version-contract checks on the exact candidate commit.
- Verify README/setup documentation, backups/recovery, release provenance and branch protection.
- Exit: all required checks pass, blockers are resolved or explicitly release-blocking, and an authorized repository administrator confirms governance settings.

## Alpha.5 hardening priorities

### 1. Authoritative CI qualification

Required evidence:

- complete Python test matrix on Ubuntu, Windows and macOS
- supported Python versions 3.10 through 3.13
- Ruff check and format validation
- MyPy validation
- native Rust/desktop format and compilation checks
- version synchronization contract
- deterministic audit evidence generation
- CodeQL
- Python dependency audit
- pull-request dependency review

The canonical required application gate is `CI / Required`. The canonical security gate is `Security / Required`.

### 2. Repository governance

The intended GitHub configuration is:

- `main` as the repository default branch
- pull requests required before merge
- required approval and Code Owner review
- stale approvals dismissed after new commits
- required CI and Security gates
- branch-current requirement
- resolved conversations
- no force-push or branch deletion
- administrator enforcement

The source-controlled policy is documented in `.github/BRANCH_PROTECTION.md`. GitHub-side administration must be completed with an account that has repository administration permission.

### 3. Runtime integration qualification

Before the next prerelease:

- exercise the CLI, web and native clients against the same shared runtime contracts
- exercise long-running team pause/resume/stop flows
- verify persistence and recovery across process boundaries
- verify research evidence and conflict quality gates end to end
- verify provider failover under initialization and request failures
- verify artifact containment and local-client boundaries on each supported platform

### 4. Provider and research reliability

Continue hardening:

- provider capability and error normalization
- rate-limit and retry behavior
- research source availability and deterministic capture
- evidence provenance and citation completeness
- bounded research coordination and resource budgets
- graceful behavior when optional providers or tools are unavailable

### 5. Documentation and compatibility

Keep these synchronized with implementation:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/MULTI_AGENT_PLATFORM.md`
- `docs/ORCHESTRATION.md`
- `docs/VERSIONING.md`
- `CHANGELOG.md`
- `AGENTS.md`

Historical audits and planning documents must identify their snapshot date and must not be presented as current implementation status.

## Release progression

The current snapshot is `0.3.0-alpha.5` and remains unreleased.

The next release decision should be based on current CI/security evidence and end-to-end qualification, not on elapsed time or historical task completion percentages.

Release readiness requires the version contract, full test/lint/type/native validation, security/dependency validation, changelog accuracy, immutable tagging and the documented main-branch governance controls.

## Long-term evolution

After alpha stabilization, larger initiatives can be considered without treating them as release blockers:

- richer native/Rust integration
- expanded memory and model capability intelligence
- broader protocol compatibility
- performance and concurrency optimization
- packaging/distribution improvements
- reproducible build and benchmarking infrastructure

These are subordinate to correctness, security, compatibility and maintainability of the existing platform.

## Detailed implementation work packages (authoritative review, 2026-10-13)

The gates above define qualification order. This section maps them to current source and existing tests, and defines the minimum work products. Paths named as “targets” are current locations to refactor or extend, not a requirement to create a parallel module for every noun. Keep PRs small enough that reviewers can inspect the behavior change and its exact test evidence.

### Gate 1 work package — establish repository truth

**Inspect and qualify first**
- Confirm the actual default branch and current heads using GitHub, then reconcile master/main using ordinary PR merges only. The repo currently has both branches, and the intended canonical branch differs from the reported default.
- Verify branch protection/rulesets with an administrator. A markdown policy or passing workflow is not GitHub enforcement.
- Review .github/workflows/ci.yml and .github/workflows/security.yml. The current CI has a Python OS/version matrix, Ruff, a limited strict MyPy target list, version checks and Rust format/compile checks. It must gain Rust tests and frontend tests as those parts become implemented.
- Treat docs/CODEBASE_AUDIT.md, docs/CONTEXT.md and docs/implementation_plan.md as dated/historical wherever their notices say so. Do not use stale line counts or feature-completion tables as proof of current behavior.

**Deliverables and exit tests**
- One current baseline summary tied to a commit.
- Confirm CI and Security are triggered for the active PR base and exact candidate head.
- Verify the synchronized version contract, current tests and build steps.
- Exit only after branch/default/protection facts are confirmed, not inferred from source docs.

### Gate 2 work package — one identity and tenant authorization model

**Implementation order**
1. Specify principal, tenant, membership, workspace and session in docs/STORAGE_AND_GOVERNANCE.md; use server-generated stable IDs and a documented local-mode bootstrap identity.
2. Introduce one request authentication/principal dependency and one policy decision interface. Do not let each route invent its own local-host check or permission logic.
3. Convert security-sensitive routes gradually, starting with API surface inventory and read/list paths, followed by mutations, downloads/exports, WebSockets, cancellation/resume and replay.
4. Update run/team/research/memory/artifact/service queries to require ownership scope. A random ID, path or connection address is not a grant.
5. Rework process-global state used for workspace, active session and provider choice so each request/run uses an explicit context. Parallel users must not overwrite one another's mutable execution context.
6. Preserve local operation through an explicit local principal. Do not use a special “loopback is administrator” bypass.
7. Add membership/session revocation and background-worker checks before multi-user deployment is even considered.

**Current first-change candidates**
- src/nexus_agent/auth/web_routes.py and src/nexus_agent/auth/store.py: retain local provider credential management but separate credential ownership from login/session identity.
- src/nexus_agent/gui/server.py and the route registrars in agents, team, MCP, memory, audit and research: centralize principal resolution and enforce policy before data access.
- src/nexus_agent/storage/layout.py, src/nexus_agent/session/manager.py, src/nexus_agent/team/store.py and src/nexus_agent/memory/scoped.py: make ownership and run context explicit; do not assume existing filesystem scopes equal tenants.

**Required acceptance tests**
- No principal, expired session, revoked session and invalid/rotated session fail closed on every protected operation.
- Tenant/user A cannot list, read, update, delete, download, export, search, stream, replay, cancel or resume tenant/user B data by guessing IDs or changing body/query/header values.
- Revoked workspace membership is enforced by workers and active streams, not just new API requests.
- Concurrent runs in separate workspaces/providers do not leak memory, provider credentials, working directory, messages, cancellation or artifacts.
- Tests exercise both normal access and denials; do not call Gate 2 complete merely because a remote-IP request returns 403.

### Gate 3 work package — contract-first shared services

**Implementation order**
1. Extract domain operations from FastAPI endpoint bodies into service functions while retaining existing URLs.
2. Establish stable request/response DTOs and explicit lifecycle/error enums. Version new contracts and provide compatibility adapters for current GUI/CLI callers.
3. Extend the existing src/nexus_agent/protocol/agent_protocol.py boundary where appropriate instead of creating a second protocol by default.
4. Generate OpenAPI from API models; generate TypeScript client types from that contract. Runtime validation is still required for JSON/WebSocket payloads.
5. Define a durable event envelope and sequence/replay contract. Append an event transactionally before publishing it to any connected client.
6. Add idempotency to run creation and other mutations whose retries can cause duplicate side effects.
7. Make native IPC framing, message size, cancellation, errors, protocol version and shutdown explicit.

**Exit tests**
- Same command produces the same domain state through HTTP, CLI/IPC and desktop.
- Existing local routes and clients work during migration.
- Contract tests reject malformed input and prove compatibility or an intentional version break.
- Event-gap/reconnect tests reconstruct a coherent snapshot; duplicate events are deduplicated; secrets are absent from payloads.

### Gate 4 work package — bounded agents, tools and run execution

**Current implementation starting points**
- src/nexus_agent/team/planner.py, runtime.py, models.py, control.py, store.py and tools.py.
- src/nexus_agent/agents/models.py and registry.py (where applicable).
- src/nexus_agent/permissions/ and the shared tool implementations in src/nexus_agent/tools/.
- src/nexus_agent/workflows/registry.py and src/nexus_agent/core/agent.py.

**Implementation order**
1. Formalize the typed plan contract and reject unknown dependency IDs and cycles before dispatch.
2. Represent each run/task with explicit context, permissions, provider route, budget and cancellation signal.
3. Move mutable planner/session/provider selection out of process-global state and into run/request-scoped contexts.
4. Make task transitions validated and durable; introduce worker heartbeat/lease and restart reconciliation.
5. Route every tool call through argument-schema validation and a current policy decision.
6. Bound agent count, plan revisions, concurrency, tool calls, retries, time, provider cost and output volume. Define behavior at every limit.
7. Make side-effecting operations idempotent or recovery-aware before allowing automatic retries.
8. Record final synthesis separately from worker outputs and require reviewers/verifiers for workflows that declare them.

**Exit tests**
- DAG success/failure/cycle/missing-dependency cases.
- Worker crash, lease expiry, hung subprocess, partial result, repeated delivery and resume-after-restart.
- Cancellation terminates cancellable work and records non-cancellable side effects.
- A generated agent cannot grant itself shell/write/network/credential access.
- No failed or cancelled required verifier is silently represented as a successful run.

### Gate 5 work package — tenant-aware persistence, research and memory

**Implementation order**
1. Preserve local SQLite behavior and introduce repository interfaces around existing team/research/session/memory stores.
2. Add PostgreSQL migrations and transaction-aware repository implementations for shared mode. Use one logical data model and test semantic differences between SQLite and PostgreSQL.
3. Add tenant/workspace ownership and indexes to all tenant-owned objects. Use database constraints and transaction boundaries in addition to service policy.
4. Introduce an ArtifactStore interface: local filesystem adapter for personal mode; private object-storage adapter when required by shared deployment. Store ownership, hashes, content metadata and retention in the database.
5. Ensure memory candidate retrieval filters by authorized scope before ranking and retrieval. Isolate user, project, workspace, agent, team and session scopes.
6. Ensure provider credentials stay in a secret store; ordinary rows/config contain references and non-secret metadata only.
7. Preserve evidence-first research: immutable source snapshot, exact quote, claim record, verification record, contradiction state and final evidence gate.
8. Define schema/data upgrades, import of legacy local data, backup/restore, delete/retention and secret rotation.

**Exit tests**
- Repository contract tests for create/read/update/delete/list, transaction rollback, concurrent writes and uniqueness constraints.
- Migration from a previous supported local data layout without loss or accidental sharing.
- Backup/restore and crash/restart tests.
- Cross-tenant memory, artifact, source and credential negative tests.
- timed and until_saturation modes stop at their real deadlines/budgets; user_only never gains autonomous fetch capability; evidence output links to stored sources.

### Gate 6 work package — modern clients without duplicated domain logic

**Web application**
- Current frontend source is static HTML/CSS/JavaScript in src/nexus_agent/gui/frontend. Do not claim TypeScript exists until the package/build is present and CI validates it.
- Introduce TypeScript + React + Vite alongside the current assets, configure strict type-checking, and generate API types from OpenAPI.
- Migrate one screen at a time. Start with provider catalog or agent-profile inspection; next configuration/memory; then workflow graph/activity timeline/artifacts; then authenticated chat and secret-management screens.
- Add automated browser tests for create/run/control, worker messages, live updates, approval prompts, reconnect/replay, error states and artifacts.
- Serve compiled assets from the same local FastAPI app initially. A separately deployed frontend is a later option, not a prerequisite.

**Rust clients**
- Keep nexus-rs/ as native CLI/TUI and nexus-desktop/ as a native desktop client. Each is a presentation/control surface over shared contracts.
- Add Rust unit/integration tests; existing cargo fmt/check gates only validate formatting/compilation.
- Test backend startup/termination, protocol error handling, large/Unicode payloads, reconnection, token expiry and graceful shutdown across supported operating systems.

**Exit tests**
- Same acceptance scenario passes through web, CLI/TUI and desktop with the same persisted run result.
- Frontend compiler and browser test jobs are required checks once TypeScript is introduced.
- Native client tests run in CI; UI failures and missing asset files are detected before packaging.

### Gate 7 work package — production and release readiness

- Add correlated structured logs, redaction, metrics and traces across API, scheduler, worker, provider and tool boundaries.
- Define per-tenant run concurrency, rate, token/cost, runtime and artifact limits; verify a noisy tenant cannot starve other tenants.
- Exercise graceful shutdown, run cancellation, worker lease recovery, migration, backup/restore, data deletion/retention and provider secret rotation.
- Run the full Python OS/version matrix, Ruff/format, expanded MyPy, PostgreSQL repository tests, TypeScript build/browser tests, Rust tests/builds, version contract, CodeQL, dependency audit and other required security checks against the exact release candidate.
- Ensure release tags are immutable and reachable from the verified canonical integration branch; verify build provenance and installation on supported platforms.
- Keep non-loopback/shared deployment disabled until Gate 2 acceptance evidence passes and an administrator approves the exposure policy.

### Recommended change sequencing

Treat each implementation package as a series of small vertical-slice PRs: one behavior change, one focused test set, one compatibility note and one exact-head CI result. Update architecture/API/roadmap docs in the same PR where a contract changes. Never implement all gates in one omnibus PR. Do not close a gate based on elapsed time, number of commits, UI presence or broad green checks that do not exercise the requirement.


