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
