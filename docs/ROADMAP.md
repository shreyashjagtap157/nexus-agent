# NexusAgent Execution Roadmap

> **Current baseline:** 0.3.0-alpha.4
> **Status:** Active hardening and release qualification
> **Canonical integration branch:** `main`

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
- local-only protection for sensitive team-control and team-data APIs
- guarded autonomous web fetching with private-target and redirect protection
- Python CLI/web surfaces plus native Rust CLI and desktop clients
- cross-platform CI, lint/type validation, native compilation, version contracts and security gates
- reproducible release validation and provenance-oriented packaging workflow

## Alpha.4 hardening priorities

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

The current snapshot is `0.3.0-alpha.4` and remains unreleased.

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
