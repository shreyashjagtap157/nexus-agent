# NexusAgent — Exhaustive Implementation Blueprint

> **Document class:** Architecture-to-implementation blueprint  
> **Status:** Proposed normative implementation sequence; described targets are not proof of implementation  
> **Reviewed:** 2026-10-14  
> **Repository:** https://github.com/shreyashjagtap157/nexus-agent  
> **Source baseline:** master at 27441a7822e827474b719f49fbffea96f10ee5c5  
> **Version baseline:** 0.3.0-alpha.5, an unreleased prerelease

This document translates the existing product and architecture requirements into a single implementation strategy. It expands the gates in ROADMAP.md; it does not supersede the product contracts in ARCHITECTURE.md, MULTI_AGENT_PLATFORM.md, ORCHESTRATION.md or the proposed Gate 2 contract in STORAGE_AND_GOVERNANCE.md.

It distinguishes **observed repository facts**, **recommended decisions**, **target behavior**, **qualification evidence** and **unresolved choices**. No feature described here should be reported as implemented until the live code, tests and exact-commit workflow evidence prove it.

---

## 1. Executive decision

NexusAgent should be built as **one shared, Python-first agent runtime with language-neutral contracts and multiple client experiences**. It should not be rewritten as a Rust-only application, split into independently evolving orchestration implementations, or made remotely accessible before its identity and tenant-isolation gate is complete.

### 1.1 Language allocation

| Area | Language / framework | Responsibility | Boundary rule |
|---|---|---|---|
| Agent runtime, planners, scheduler, research, providers, tools, policy | Python 3.10+; asyncio where appropriate; typed domain models | All execution and business semantics | One canonical implementation; no client-specific orchestration |
| HTTP/API service | Python, FastAPI, Pydantic | Authentication, validation, use-case invocation and streaming | Routes are thin; policy also applies in services and repositories |
| Rich browser UI | TypeScript, React and Vite as an incremental target | Workflow visualization, event streams, settings, approvals and artifacts | Generated API types; no duplicated business logic |
| Existing CLI/TUI | Rust with the existing clap/Ratatui/crossterm/JSON IPC stack, alongside the currently supported Python CLI | Native terminal presentation, process lifecycle, keyboard handling | Python runtime remains authoritative; no second task engine |
| Existing desktop client | Rust and the existing eframe-based desktop crate | Native windowing, OS integration and presentation | Use versioned contracts; do not duplicate orchestration |
| Domain persistence | PostgreSQL for shared multi-user deployments; SQLite for personal/local deployment behind repository contracts | Ownership, state transitions, events and durable records | SQLite files or workspace folders are not tenant authorization |
| Wire contracts | Versioned OpenAPI/Pydantic schemas, JSON and documented event envelopes | Stable request, response, error, ID and event formats | Generate TypeScript DTOs and test client compatibility |
| Memory | Existing SQLite/FTS components first, behind scope-aware repositories | Local retrieval and memory persistence | Authorization filtering before ranking and prompt assembly |
| Config and profiles | YAML/TOML/Markdown as data formats with schema validation | User preferences, agent definitions and provider configuration | Data can request capabilities but cannot grant permissions |
| CI and packaging | Python tooling, Rust build tooling, GitHub Actions YAML, limited shell/PowerShell | Reproducible build and qualification | Workflows, not historical notes, prove cross-platform status |

**Python is the recommended sole language for the core.** Agent orchestration depends on quickly evolving provider APIs, research/data processing, structured tool calling and local-inference ecosystem integration. Rust is useful at native/system boundaries; TypeScript is useful for the browser experience. Neither should independently own run state, provider routing, authorization or scheduling.

Do not add Go or a second backend runtime. Do not move inference dispatch into Rust merely because an older hybrid proposal suggested it. Measure performance and correctness before considering that additional boundary.

**Do not rewrite the repository to fit a diagram.** Preserve working modules, introduce explicit domain contracts around them, migrate one vertical slice at a time, maintain compatibility adapters temporarily and remove them only after tests prove parity.

---

## 2. Product model and invariant requirements

NexusAgent is a general-purpose agent platform for software development, research, analysis, planning, automation, document/artifact work and other user-defined tasks. Research is a first-class workload, not the product boundary. Single-agent runs and multi-agent teams use the same runtime contracts.

The web app, Python CLI/TUI, native Rust CLI/TUI and desktop client are presentation/control surfaces over shared services. They must not each implement orchestration, durable run state, provider/model routing or permissions.

### 2.1 Invariants

1. **One canonical execution engine.** Single-agent and team runs share tool, provider, policy, event and persistence contracts.
2. **Local and multi-user are both initial architecture requirements.** Local operation must not require hosted identity. Multi-user must not require a later data-model rewrite.
3. **Remote/shared exposure remains gated.** Non-loopback API binding stays disabled until authenticated identity and tenant isolation pass. Loopback, CORS, origin checks, random IDs and TLS do not establish a Principal.
4. **Autonomy is bounded by runtime policy.** Harmless operations may proceed without repeated approval when the policy permits them. The runtime decides; the model does not.
5. **Generated agents cannot grant themselves permissions.** Prompts, agent profiles, retrieved documents, peer messages and MCP outputs are untrusted data.
6. **Runs have hard budgets.** Agent count, delegation depth, concurrency, time, tokens/cost, retries, tool calls, output, memory and artifacts are bounded.
7. **State is durable and replayable.** Restart or reconnect must not invent progress, lose the stop reason or silently replay a non-idempotent side effect.
8. **Ownership is server-side.** Read, write, list, export, download, stream, replay, cancel, resume and delete are authorized against live resource ownership and grants.
9. **Evidence stays traceable.** Research separates source text, extracted claims, analysis, verification and unresolved contradiction.
10. **One source of business truth.** Compatibility adapters are temporary; unsynchronized implementations are not accepted.
11. **Correctness precedes optimization.** Performance improvements preserve results, ordering, scope, path containment and error behavior unless a deliberate contract change is reviewed.
12. **Done means evidence.** Code or documentation alone is not proof of completion.

### 2.2 Non-goals for the first secure shared deployment

Do not begin with Kubernetes, dozens of microservices, a Rust-only agent engine, a custom authentication protocol or a distributed queue by default. Start with a modular Python service and a separately invokable bounded worker. Personal use should run without cloud infrastructure. Split components only when a measured deployment, performance or security requirement needs it.

---

## 3. Repository baseline: observed facts and consequences

This is a source-based snapshot, not an assertion that every endpoint has been audited.

### 3.1 Facts observed in the repository

- GitHub reports **master** as the default branch at the reviewed snapshot. A separate **main** branch exists; documentation saying main is canonical does not alter GitHub repository settings.
- Python package and Rust crates report **0.3.0-alpha.5**. This is an unreleased prerelease, not a stable API guarantee.
- Python code includes a real AgentLoop, provider interfaces/adapters, local inference/runtime selection, tools, permission handling, scoped memory, sessions, FastAPI routes, team runtime and research/evidence components.
- The web frontend currently lives as static assets under the Python GUI package. TypeScript/React is an incremental target, not a claim that the current browser app already uses it.
- The Rust repository includes a CLI/TUI using clap, Ratatui, crossterm and JSON/stdio IPC, and a desktop client using eframe with HTTP/JSON. These are real client surfaces and should be preserved.
- The team platform uses SQLite-backed local state; documented local team storage includes a workspace runtime blackboard.
- The GUI server has process-global workspace, configuration, engine/provider, memory/session and team-related state. That is compatible with a local process but is not a tenant-isolated service model.
- Existing session persistence stores session metadata and messages but does not establish the complete tenant/owner/workspace model required for shared deployment.
- Provider credentials are kept separate from ordinary configuration and have keyring/file backend options. That separation alone does not enforce user/tenant ownership, credential sharing grants or access logging.
- Non-loopback GUI/API binding is now intended to fail closed, and browser-origin checks exist. These are exposure/CSRF mitigations, not authenticated multi-user identity.
- The current security documentation says command execution is constrained but not a complete OS-level sandbox.
- CI includes a broad OS/Python matrix, Ruff, scoped MyPy, Rust checks, version checks, audit/security and governance diagnostics. A governance advisory pass is not proof that GitHub default-branch or protection settings changed.

### 3.2 Gaps that should be fixed at root cause

| Risk | Root cause | Insufficient patch |
|---|---|---|
| Process-global workspace/provider/session can cross request boundaries | Mutable execution state is not rooted in an authenticated run context | Add a login page but keep globals authoritative |
| Guessed IDs or paths may access records without tenant predicates | Repositories lack universal ownership enforcement | Generate longer UUIDs |
| Session/message rows lack tenant and owner references | Persistence predates the multi-user contract | Filter list endpoints only |
| Credentials are provider-keyed without full tenant grants | Credential reference model is not owner-aware | Add a tenant selector in UI |
| WebSocket session path is client supplied | Connection authority is not a verified Principal | Trust session ID as authentication |
| Background workers inherit broad context | No universal run-scoped capability context | Guard only the HTTP route |
| Shell/path checks are treated as sandboxing | Host execution isolation is incomplete | Assume shell=False prevents malicious effects |
| Older design docs conflict | No single actionable bridge from requirements to implementation | Leave both strategies unqualified |

---

## 4. Target architecture and trust boundaries

Separate the system by responsibility and authority, not by fashion. Local mode may host several logical modules in one process. Shared deployments can split API and workers into separate processes without changing the domain contract.

    CLIENTS
      Browser UI (TypeScript) | Python CLI/TUI | Rust CLI/TUI | Rust desktop
                                    |
                     Versioned REST and event contracts
                                    |
    API / CONTROL PLANE
      Authentication -> verified Principal -> tenant/workspace resolution
      Request validation -> authorization policy -> application use cases
      Durable run control, sessions, provider configuration, artifacts
                                    |
    DOMAIN SERVICES
      Run service | Task graph | Orchestrator | Agent registry
      Tool gateway | Provider routing | Research evidence | Scoped memory
                                    |
    EXECUTION PLANE
      Bounded worker pool -> run-scoped AgentLoop workers
      independent cancellation / budget / grants / provider references
                                    |
    PERSISTENCE AND ADAPTERS
      SQL repositories -> SQLite local / PostgreSQL shared
      scoped memory | artifact storage | credential backend
      durable run events | audit | transactional outbox / leases
                                    |
    OBSERVABILITY
      structured redacted logs | trace/correlation IDs | metrics | health

### 4.1 Trust boundaries

1. Browser, terminal, desktop, file, prompt and tool inputs are untrusted even in local mode.
2. API middleware/dependencies verify credentials and create the Principal; the Principal is not accepted from request JSON or arbitrary headers.
3. Application services authorize actions against current resource ownership and grants.
4. Repositories include tenant/owner/workspace predicates in reads and mutations. Service and data-access checks reinforce each other.
5. Workers get an immutable run context and only the capabilities needed for that run. They do not inherit blanket global access.
6. Tool adapters re-authorize every invocation and validate inputs, outputs, paths, URLs, sizes and process limits.
7. Persistent records store explicit owner/provenance IDs. An external identifier or path is a locator, not authority.
8. UI clients render policy and state; they never decide who may read or mutate a resource.

### 4.2 Local and shared profiles

**Local/personal**
- Bootstraps an explicit local Principal and personal Tenant.
- Binds to loopback by default and rejects non-loopback binding until shared-access qualification passes.
- Uses SQLite when its locking, transaction, recovery and migration behavior satisfies the local profile.
- Uses the existing credential/keyring adapters via an interface.
- May embed the worker runtime, but each run still owns context, cancellation, budgets, provider choice, policy and events.
- Imports legacy data under a single explicitly approved local owner/tenant.

**Authenticated multi-user**
- Uses established identity integration, verified sessions and no anonymous fallback.
- Uses PostgreSQL with tenant-aware schema and transactional migrations.
- Does not use global mutable workspace/provider/session state as shared authority.
- Scopes artifacts, memory and credentials to user/tenant/workspace grants.
- Enforces per-tenant concurrency, duration, storage, spending and tool budgets.
- Requires trusted transport security, but TLS never substitutes for application authorization.
- Cannot be enabled by merely changing the bind host.

### 4.3 Deployment simplicity rule

Begin with a modular monolith and a separately invokable worker role. Use clear interfaces for identity, persistence, providers, events and tools. Introduce Redis, distributed queues, Kubernetes or service discovery only when measured load or operations require them. Personal mode must not depend on those services.

---

## 5. Language and framework decisions

### 5.1 Python — authoritative domain runtime

Python owns:
- AgentLoop, model/tool calls, streaming response handling and synthesis;
- team planning, profile selection, dependency DAG, bounded scheduling and independent review;
- research collection, snapshots, evidence ledger, quote verification and contradiction analysis;
- provider adapters, capability mapping, fallback, usage/cost and secret reference resolution;
- tool definitions, authorization hooks, MCP integration, filesystem operations, shell/browser adapters;
- session/run/task/event/memory/repository service layer;
- FastAPI request validation, REST endpoints, event delivery and local service;
- local model discovery and inference adapters.

Continue type annotations, Pydantic at I/O boundaries, Ruff and strict MyPy on the critical path. Keep synchronous model and tool libraries off the event loop. If AgentLoop emits synchronous iterators, wrap execution in bounded workers with cancellation propagation. Do not let one blocking tool freeze API health, cancellation or every other run.

Use asyncio for I/O-bound work. Async does not make CPU-bound model generation parallel, nor does it justify unlimited tasks. Model concurrency uses bounded worker slots/processes and explicit engine lifecycle management.

### 5.2 TypeScript — browser experience

Introduce TypeScript incrementally for the richer console as workflows, event streams, team graphs, approvals, agent profiles and artifact inspection grow.

Recommended shape:
- TypeScript, React and Vite;
- generated API models from canonical OpenAPI/Pydantic schemas;
- one typed API client for request IDs, errors, authentication behavior and event reconnect;
- real server-derived events rather than simulated progress;
- reusable state/data components and accessible interactions;
- tests for event replay, cancellation races, expired sessions, long output and API failures.

Do not migrate the whole UI before the API and run/event contracts stabilize. Start with one vertical slice: run list, run detail, event stream and artifacts. Extend to team graph, agent editor, provider settings and memory browser after end-to-end parity works.

### 5.3 Rust — native clients and narrow system boundaries

Keep the existing Rust crates for native terminal/desktop experience. Rust owns rendering, keyboard behavior, desktop packaging, OS integration, terminal restoration, subprocess supervision and typed decoding of versioned contracts.

Do not move the planner, provider routing, team scheduler or research pipeline into Rust solely because Rust is already used. The older HYBRID_ARCHITECTURE.md proposal included direct Rust inference dispatch and aggressive startup/latency goals. Treat those details as historical options, not binding requirements. A Rust inference path requires measured CPU/GPU benchmarks plus equivalent behavior, memory use, tool calling, fallback and support cost. Otherwise, keep model/provider semantics in Python.

Native clients must call shared services/IPC contracts and render canonical state. They must not import hidden mutable state, bypass API authorization or build a separate task engine.

### 5.4 Other data and automation languages

- SQL and migration scripts for database schemas and constraints.
- JSON for wire messages and event envelopes.
- YAML/TOML for declarative configuration only, with schema validation.
- GitHub Actions YAML for CI/release workflows, with least-privilege permissions and reviewed/pinned actions.
- Small shell/PowerShell scripts only where cross-platform behavior is explicit and tested.
- No second server language, custom DSL or Rust inference service without an approved ADR.

### 5.5 Database libraries

Introduce SQLAlchemy 2.x and Alembic for the tenant-aware relational domain plane, migrating existing SQLiteStore components gradually. Official references:
- SQLAlchemy ORM: https://docs.sqlalchemy.org/en/20/orm/
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- Alembic migrations: https://alembic.sqlalchemy.org/en/latest/tutorial.html

Use one repository contract and one authoritative write path per entity. Existing FTS5-specific memory code can remain behind its own repository interface during migration. An async database session/transaction must not be concurrently shared across tasks. Each service operation has its own transaction scope, and connection usage is bounded.

---

## 6. Domain modules and dependency direction

These are desired logical boundaries, not an instruction to rename every current file immediately.

| Module | Responsibility | Existing surface to adapt |
|---|---|---|
| identity | Principal, identity adapter, local bootstrap and session lifecycle | auth and GUI request handling |
| tenancy | tenants, memberships, workspace grants and roles | scattered route guards and storage scopes |
| policy | action/resource authorization, capability resolution and approvals | permission manager, profile grants and route-local checks |
| api/v1 | versioned DTOs, REST routes, SSE/WebSocket adapters and errors | GUI and route modules |
| application | use cases: create/cancel/resume run, generate agent, store memory, export artifact | route/CLI handler logic |
| runs | lifecycle, state transitions, idempotency and recovery | sessions/team integration |
| orchestration | plan, DAG, dependencies, scheduler and review | team runtime/planner/task graph |
| agents | profile schema, registry, generation, provenance and validation | AgentRegistry/AgentGenerator |
| workers | durable dispatch, leases, bounded execution and cancellation | current team worker lifecycle |
| providers | catalog, capability, model routing, fallback and secret reference | provider factory/adapters |
| tools | schemas, risk class, capability grant and safe execution adapters | tool implementations |
| sandbox | OS-specific process containment, path/network policy and resource limits | existing core sandbox |
| memory | owner scopes, retrieval filters, retention and deletion | MemoryManager/ScopedMemory |
| research | source policy, snapshots, claims, verification and synthesis | research routes/store |
| persistence | ORM, repositories, migrations, transactions and health | SQLiteStore/session/team stores |
| artifacts | authorized manifest, content storage, export/download and retention | workspace/runtime files |
| events | durable run events, replay cursors and delivery | WebSocket/team event handling |
| audit | actor/tenant/action/target/outcome and safe redaction | audit routes/store |
| observability | structured logs, traces, metrics, health and run summaries | usage/telemetry |
| clients | generated API client and typed IPC contracts | static frontend, nexus-rs, nexus-desktop |

### 6.1 Dependency direction

Domain/application services must not import FastAPI Request, Click commands or front-end components. Routes and CLI commands call application services. Application services depend on domain models, policy, repositories and ports. Repositories implement data contracts. Provider/tool adapters implement explicit protocols and receive scoped context.

A healthy operation is:

    request
      -> authenticate and create Principal
      -> validate the external command
      -> application use case receives Principal + command
      -> authorize the action against the actual resource
      -> repository queries include tenant/owner/workspace predicates
      -> durable state and event/outbox intent are committed
      -> bounded worker is notified
      -> event adapter streams only authorized events

The same use case serves web, CLI and native client. A route-local fix does not count if downstream code still uses a global provider, active session or unrestricted workspace.

### 6.2 Global state rule

Immutable registries and process resources may be global. User/run mutable authority may not be keyed only by a process-wide active session. Replace global workspace/provider/session assumptions with an explicit request/run context incrementally, then prove isolation with concurrent-user tests.

---

## 7. Identity, tenant isolation and authorization — blocking gate

The Gate 2 contract in STORAGE_AND_GOVERNANCE.md is the starting authority. Do not enable remote/shared access until the complete gate passes.

### 7.1 Identity integration

Prefer an established OpenID Connect provider for shared deployments instead of inventing a password/token protocol. Use Authorization Code with PKCE for browser sign-in. For CLI sign-in, select a suitable device-authorization or loopback callback flow and document the provider-specific constraints. Local mode bootstraps an explicit local Principal and personal Tenant.

Internal auth stays provider-neutral. Shared mode has no anonymous fallback. A remote request lacking valid credentials remains denied even if its peer address is loopback. A TLS proxy does not supply identity unless an explicitly configured and verified proxy-auth contract says it does.

The specific identity provider is an ADR because self-hosting/operator requirements remain open. The Principal, ownership and authorization contracts should proceed independently.

### 7.2 Principal contract

Authentication creates an immutable typed Principal containing at least:
- immutable server-generated user_id;
- tenant_id selected after a current server-side membership check;
- session/authentication-session identity;
- authentication method and required assurance metadata;
- issue/expiry timestamps;
- authorization/membership version;
- workspace-grant resolution context;
- request/correlation ID for audit.

Never accept user_id, tenant_id, role, membership, ownership or authorization version directly from body/query/arbitrary headers/URL paths. Display name and email are attributes, not authorization keys. Re-check current membership so revocation and role changes take effect.

### 7.3 Session rules

- Generate high-entropy opaque session secrets with vetted library primitives.
- Persist a one-way verifier/digest when server-side revocation is needed, not the raw bearer secret.
- Rotate session identifiers at authentication and privilege changes. Enforce idle and absolute expiry, logout, revocation and recovery.
- Browser cookies use HttpOnly, deliberate SameSite, narrow Path/Domain and Secure when HTTPS is used.
- Protect state-changing cookie-authenticated requests against CSRF and validate expected origin.
- Never put long-lived tokens into URLs, telemetry, event payloads, generated profiles or ordinary config.
- CORS is not authentication.
- WebSocket auth reuses a verified session or a short-lived single-use ticket. A client-supplied session ID is not proof of identity.
- Rate-limit login/token operations; avoid user enumeration and leakage through authentication errors.

### 7.4 Tenant model

Minimum relational records:
- User: user_id, identity-provider subject, display metadata, status and timestamps.
- Tenant: tenant_id, display name/locator, status, policy/quota reference and timestamps.
- TenantMembership: user_id, tenant_id, role/status, authorization version and creation/revocation time.
- Workspace: workspace_id, tenant_id, config and lifecycle.
- WorkspaceGrant: subject/role, workspace_id, allowed action set and status.
- Session: tenant_id, owner_user_id, workspace_id, lifecycle and metadata.
- Run: tenant_id, requester_user_id, workspace_id, workflow, budget, state and cancellation/deadline.
- Task: tenant_id, run_id, parent/dependencies, assigned profile, state, attempts and result metadata.
- AgentExecution: tenant_id, run/task IDs, profile revision, capability snapshot reference and worker state.
- TeamMessage: tenant/run/team IDs, sender/recipient, message scope and timestamps.
- RunEvent: tenant/run IDs, sequence, event type/schema, actor, payload reference and timestamp.
- Artifact: tenant/workspace/run IDs, owner, opaque storage key, digest, size, media type and retention.
- MemoryRecord: owner/scope identifiers, tenant where applicable, provenance, retention/deletion and storage reference.
- ProviderConnection/SecretReference: owner, tenant, provider, credential reference, grants and status.
- AuditEvent: actor, tenant, action, resource, outcome, correlation ID and safe metadata.
- Job/Outbox: tenant/run/task context, lease, retry and dispatch state.
- IdempotencyRecord: Principal/tenant scope, operation, request hash, resulting resource and expiry.

Tenant-owned rows carry tenant_id; workspace-scoped records also carry workspace_id; individual-owner records include owner_user_id. Shared resources need explicit grants. Global immutable built-ins are modeled as global, not as accidentally ownerless tenant resources.

Random IDs are not authorization. Enforce foreign keys/constraints, scoped uniqueness, indexes and service-level policy.

### 7.5 Authorization

Centralize policy behind an entry point conceptually equivalent to:

    authorize(principal, action, resource, context) -> Allow | Deny | RequireApproval

Load resources through scoped repositories; do not infer authority from a path string. Decisions consider verified Principal, live membership, workspace grants, tenant state, resource ownership, action, tool risk and current policy. Denials provide a safe reason and a structured audit record.

Enforce authorization in three connected layers:
1. API dependency validates the Principal.
2. Application service authorizes the action and actual resource.
3. Repository query/mutation constrains tenant, owner, workspace and grant.

Cover list/read/create/update/delete, run start/cancel/resume, artifact download/export, memory/search/store/forget, event subscribe/replay, provider use/test/rotate, agent generation/save/delete, MCP configure/call, workspace read/write and admin/member management. Fail closed on missing or ambiguous ownership, session, tenant or workspace.

### 7.6 Background jobs and event isolation

Persist actor/tenant/workspace/run and authorization version with each job. Before start/resume/cancel, credential use, workspace access or protected event emission, revalidate run authority. A worker never inherits process-wide permission.

Do not publish a process-global event queue and filter in the client. Event storage, subscription and cursor replay are owner-scoped. Cancellation/reconnect cannot operate another tenant's run.

### 7.7 Legacy migration

Initial migration is single-owner local migration, not automatic sharing:
1. Detect legacy state/schema versions and offer a backup location.
2. Verify the backup before writes.
3. Create local user/tenant/workspace.
4. Assign old session, message, team, artifact, profile, memory and audit metadata to that approved local owner.
5. Keep secret material in credential storage; migrate only secret references and ownership metadata.
6. Preserve IDs where possible and add owner foreign keys/indexes.
7. Verify counts, key hashes and semantic spot checks.
8. Record repeatable migration ID and completion report; re-run safely.
9. On failure preserve original source and provide rollback/recovery.
10. Importing legacy data into a shared deployment requires explicit owner/tenant selection and audit-confirmed consent.

### 7.8 Gate 2 attack tests

With two users and two tenants, User A must not be able to list/read/change/delete/download/export/resume/cancel/subscribe/replay User B's sessions, messages, runs, tasks, team state, research evidence, artifacts, memory, agent profiles, audit events or provider credentials—even with guessed IDs, path manipulation, filter changes or event cursors.

Also test changed/revoked membership, role downgrade, tenant switch, session expiry/revocation/rotation, stale authorization version, same-machine requests without auth in shared mode, WebSocket reconnect after revocation, worker cancellation and membership revocation during active execution. Test service/repository rejection, not only route guards.

---

## 8. Persistence and artifact data model

### 8.1 Relational authority

Use the relational database for ownership-sensitive or transactional state: identities, tenant memberships, workspaces/grants, provider connection refs, sessions, runs/tasks/executions, team messages/events, artifact manifests, memory metadata, outbox/jobs, audits, idempotency and migrations.

SQLite is the supported local backend. PostgreSQL is the shared multi-user backend. A requested deployment mode must fail startup with an actionable error if the configured backend cannot fulfill its concurrency/isolation contract.

### 8.2 Repository/transaction rules

- Use SQLAlchemy 2.x and Alembic for new tenant-aware relational domains.
- Define explicit transaction scope per application use case.
- Never share an AsyncSession concurrently across unrelated tasks.
- Use conditional state transitions/version columns for run/task concurrency.
- Enforce foreign keys, tenant owner constraints and workspace references in the DB as well as Python.
- Index tenant + owner/workspace + resource ID; tenant + run + event sequence; tenant + status + dispatch time; membership and artifact owner lookups.
- Do not select all tenants and filter in Python.
- Include ownership filters in list/search/export endpoints.
- Test concurrent writes and restarts on SQLite local and PostgreSQL shared profiles.
- Version schema changes and document safe downgrade/recovery where destructive reversal is impossible.
- Use content-addressed/opaque artifact keys rather than storing unbounded payloads in high-churn relational rows.

Migrate by domain boundary, not one giant schema rewrite:
1. repository contracts and migration test infrastructure;
2. identity/tenant/workspace;
3. sessions/runs/tasks/events and worker ownership;
4. artifact manifests and provider secret references;
5. memory metadata and scope enforcement;
6. retire redundant legacy writes after parity is tested.

### 8.3 Filesystem and artifacts

An authorized workspace record selects the root. Caller-provided paths cannot select tenants.

Each file/artifact operation:
- resolves tenant/workspace and checks grants;
- resolves the authorized canonical root;
- normalizes the relative path and rejects traversal;
- defines symlink/junction behavior and checks final resolved containment;
- accounts for race conditions between validation and open/write;
- enforces content/size/count/type budgets;
- audits mutations with actor, tenant, workspace, run and correlation ID;
- avoids leaking host absolute paths in shared responses;
- uses staged writes/atomic replacement where supported and reversible trash by default;
- handles stale metadata if files change after listing;
- tests POSIX and Windows separators, case behavior, symlinks/junctions, permission errors and race scenarios.

### 8.4 Credentials/config

Ordinary config stores preferences and opaque secret references. Local mode may keep existing keyring/file adapters, with the documented limitation that ordinary local file storage is not encryption at rest. Shared mode needs tenant/user ownership, access grants, encryption at rest and rotation/deletion semantics. Resolve secrets just before an authorized provider call, redact from every error/log/telemetry path and never place raw credentials in prompts, agent profiles, event payloads or ordinary audit records.

---

## 9. Run/task lifecycle, idempotency and durable events

### 9.1 State model

Use one contract across API, persistence and clients. Recommended states:
- planned: plan exists but not dispatched;
- ready: dependencies and policy allow dispatch;
- running: active execution;
- waiting: explicit wait on approval, external result or schedule;
- blocked: no safe progress until a named condition changes;
- failed: terminal failure and reason;
- cancelled: terminal cancellation;
- completed: execution finished, optional verification may remain;
- verifying: required tests/review/evidence checks run;
- succeeded: required acceptance checks passed;
- incomplete: budget exhausted or stopped without meeting the goal.

If enum names change, publish a transition specification and migration mapping. Do not let "done" ambiguously mean worker returned and the overall task passed qualification.

### 9.2 Transition semantics

- State changes are conditional from the expected prior state/version; races do not silently overwrite.
- State transition and durable event commit together or through a transactional outbox.
- A cancelled run cannot return to running except through an explicit authorized resume.
- Retry only retryable failures, with bounded count and backoff.
- Non-idempotent tools are not replayed blindly after timeout.
- Unknown dependencies/cycles fail explicitly; dependent tasks get a terminal blocked/failed outcome.
- Budget exhaustion creates a documented stop/wait outcome; an agent cannot ask to plan forever.
- Pause is a durable control intent; show pending versus acknowledged pause/cancel.
- Persist final verification result, artifacts, failure reason and unresolved issues.

### 9.3 Idempotent dispatch

Accept an idempotency key scoped to Principal/tenant and operation. Store key, normalized request hash and resulting resource ID. Same key + same request returns the same result; same key + different body fails.

Use a transactional outbox or equivalent mechanism so run/task state and dispatch intent commit together. A bounded worker claims jobs with lease/heartbeat semantics. Since delivery may occur more than once, transitions and tool calls must be duplicate-safe.

Do not start with Redis by default. A PostgreSQL outbox/lease table plus bounded workers is a reasonable shared-deployment starting point; local mode can use the same dispatcher embedded in the local service. Add an external queue only when measured throughput demands it.

### 9.4 Event envelope

Each durable event includes schema_version, event_id, tenant_id, run_id, optional task/execution/session IDs, monotonic per-run sequence, event_type, actor type/ID, timestamp, correlation/request ID, safe structured payload/reference and state version.

Do not expose credentials, unrestricted tool payloads or hidden/private reasoning traces in events. Store intentional status, bounded/redacted tool summaries, approved user-visible outputs and outcome messages.

Authorize run ownership before any subscription or replay cursor is processed. Store durable event history or checkpoints sufficient to reconstruct current state. Apply retention and deletion policy.

### 9.5 Streaming/reconnect

Use SSE for one-way dashboard updates when sufficient; keep WebSocket for bidirectional chat/control or native IPC if needed. Both follow the same durable event contract:
- authenticated connection and authorized run;
- server-side cursor/replay validation;
- message/subscription bounds, heartbeat and explicit disconnect reason;
- stable sequence numbers;
- no process-global fan-out as authority;
- reconnect after dropped network, replay gap recovery and expired/revoked session tests.

---

## 10. Agents, planning and execution

### 10.1 Profiles are not permission grants

Profiles hold stable ID/schema revision/provenance, scope, role, mission, instructions, requested tool categories, reviewer role, dependencies, provider/model preference references and validation/enable state. They cannot grant credentials or permission.

Generated profiles are editable and reusable. Generation returns structured data, then schema validation checks duplicate IDs, unknown dependencies, invalid scopes/tools, instruction length, unsupported capability requests and provenance before saving. Do not execute partially valid output.

### 10.2 Bounded planning protocol

1. Validate goal, workspace, policy and acceptance criteria.
2. Select a named workflow (code-change, build-review, research-verify, exhaustive-research, architecture-debate, repository-audit or automation).
3. Create one bounded plan and typed DAG.
4. Reuse pinned/saved profiles and select matching reusable roles.
5. Generate only missing specialists, with depth/count/cost limits.
6. Validate dependencies, cycles, duplicate roles, budget and capability policy.
7. Freeze the plan revision and execution budget.
8. Dispatch dependency-ready tasks in bounded waves.
9. Record results/failures and update durable state.
10. Run review/synthesis/evidence gates required by workflow.
11. Stop when acceptance criteria pass, budget expires or a terminal blocker exists.
12. Persist outcomes, proof, artifacts and unresolved work.

The documented research protocol bounds post-deployment coordination to 5–10 dependency-aware waves. Planning is a one-time deployment stage; execution must not recursively regenerate teams without bound.

### 10.3 Run-scoped worker context

Every run owns planner state, task DAG revision, cancellation/deadline, budget counters, workspace/path grants, provider/model route, secret references, memory scope, event cursor, audit context and worker messages/artifacts.

Each AgentLoop receives this context explicitly. Cross-worker communication uses versioned messages and artifacts, not uncontrolled shared mutable Python dictionaries. Use immutable defaults; state changes go through services/repositories and events.

### 10.4 Scheduler

- Compute ready tasks from a validated DAG.
- Reject unknown dependencies/cycles before dispatch.
- Apply per-run and per-tenant concurrency limits.
- Use explicit priority/fairness policy to avoid starvation.
- Persist worker leases and dispatch intents.
- Propagate cancellation/deadlines into workers and children where possible.
- Retry only transient failures within a fixed budget.
- Release resources on worker failure and recover expired leases.
- Mark dependents blocked/failed rather than leaving them pending forever.
- Ensure a stale worker cannot overwrite a newer transition or emit duplicate terminal events.

### 10.5 Autonomy and approval

Default to autonomous execution within policy. Harmless reads/searches/source verification can proceed without repeated approval when allowed. Writes, process execution, commits, network actions, credentials and destructive operations are risk-classified and evaluated against Principal + tenant + workspace + tool + arguments + policy.

Support allow/ask/deny, scoped grants, approval lifetime, policy version/reason and audit records. Approval covers exact reviewed arguments and context; modified arguments require re-authorization.

---

## 11. Tools, shell and MCP

### 11.1 Uniform tool contract

Every tool declares stable name/version, input/output schema, capabilities, risk, scope, side effects, timeout/resource limits and safe errors. The registry exposes only eligible tools to a run, but every invocation is checked again during execution.

Per call: validate name/schema -> resolve run context -> authorize exact operation -> obtain required approval -> enforce timeout/output/cancellation -> execute adapter -> sanitize output/errors -> write safe event/audit -> update budgets and state.

### 11.2 Filesystem operations

Use workspace-rooted canonical paths and enforce containment on every operation. Define symlink/junction policy, hidden-file/exclusion semantics, deterministic ordering, large-file behavior and permission-error behavior as endpoint contracts. Destructive deletes use reversible trash by default. A path supplied by a model/tool never selects the tenant or workspace.

### 11.3 Shell and process execution

Avoid implicit shell interpretation and continue using argument vectors where applicable. However, this is not a complete sandbox. Add platform-specific OS containment appropriate to permitted risk:
- workspace and filesystem boundaries;
- network egress and private-target/redirect policy;
- executable/command restrictions;
- sanitized environment and authorized secret injection;
- CPU/memory/process/time/output limits;
- child process cancellation, termination and reaping;
- least privilege (no root/admin for ordinary runs);
- process/container/OS sandbox for untrusted code where supported;
- explicit unsupported-platform guarantees.

Do not claim equal cross-platform isolation until each platform is tested. Do not allow tool output to become system policy. Avoid exposing secrets through command arguments/environment unless an explicitly reviewed mechanism requires it.

### 11.4 MCP

MCP servers are external capabilities with individual trust boundaries. Validate configuration and tool schemas, authorize each invocation, separate server credentials by Principal/tenant, enforce time/size bounds, clean up process lifecycles, audit outcomes and redact errors. Treat server output as untrusted. Shared MCP settings require authenticated owner-scoped routes.

---

## 12. Provider, model and credential plane

### 12.1 Provider interface

Keep a provider-neutral contract for capability discovery, model selection, tool calling, streaming, context limits, structured output, usage/cost and failure classification. Adapters normalize transient/permanent/auth/rate-limit/invalid-model failures, use connection/request timeouts, apply bounded retry only to safe operations, propagate cancellation and report effective model/provider plus fallback reason.

Agent role preferences do not select unauthorized models. Model fallback cannot change policy or reveal credential detail. Provider/model use consumes tenant budgets.

### 12.2 Routing

Routing considers task capability, allowed provider connections, availability, cost budget, explicit fallback and policy. Record effective route and reason in the run. Avoid hard-coding one user's provider/model setup into task orchestration.

NVIDIA NIM and OpenAI-compatible endpoints belong in the provider adapter/catalog framework. Validate endpoint/model ID/protocol/credential reference/timeouts/capabilities separately. Do not assume one NIM model identifier or endpoint works for all user credentials.

### 12.3 Credential controls

Local mode may use existing keyring/file storage with documented security limits. Shared mode requires tenant/user-owned connections, authorized sharing grants, encryption at rest, key rotation, use/audit trails and deletion.

Create/use/test/rotate/revoke are separate operations. Existing secrets are never returned in config responses. The server resolves secret just before a provider request, after authorization. Redact all errors/logs/tool output. No raw credential may be copied into prompts, profiles, task plans, events, memory or normal audit records.

---

## 13. Memory and research isolation

### 13.1 Memory scopes

Keep explicit global, user, project, workspace, agent, team and session scopes but make owner semantics precise:
- global: curated read-only material, write only via maintainer process;
- user: private to a verified user unless explicitly shared;
- project/workspace: associated with authorized project/tenant scope;
- agent/team/session: owned by the profile/team/run/session with explicit sharing rules.

Scope name does not imply authority. Resolve owner from Principal and authorized resource record, not caller-invented IDs. Each entry has provenance, timestamps, owner/scope, retention and deletion state.

### 13.2 Retrieval filters

Filter sources by authorization **before** search/ranking/reranking/prompt assembly. Never query a shared index and rely on the model to ignore other tenants' records. Cache keys incorporate tenant, user/policy version, workspace and scope where results vary by authorization. Invalidate caches after revocation/deletion and preserve provenance through retrieval.

### 13.3 Memory lifecycle

A permanent memory write is not automatic just because a model produced text. Require explicit product policy or a consolidation step. Support search, inspect, edit, forget, export, retention, deletion and migration. Deletion must update secondary indexes and caches; backup retention policy must be documented.

Existing SQLite FTS5 is a reasonable local starting point behind a repository interface. For shared use, choose concurrent storage that enforces tenant filtering before retrieval. Benchmark PostgreSQL full-text/vector features before adding a separate vector service.

### 13.4 Research evidence

Research contracts remain:
- source mode: user_only, hybrid, autonomous;
- collection mode: single, timed, until_saturation, continuous;
- depth affects real source breadth, verification, contradictions, review and stop rules.

user_only must not autonomously discover/fetch unapproved external sources. Timed must stop on deadline, even with blocked workers. until_saturation uses measurable novelty/marginal yield plus a hard maximum. continuous requires cancellation, retention and budgets.

A source record contains canonical URL/local document ID, retrieved timestamp, digest, source type/method and retention permission. Store snapshots where allowed. Claims reference exact supporting quotations, verifier state, contradiction/reviewer status and source metadata. The capture layer fetches content itself; worker-supplied text is not authoritative source proof. Changing evidence invalidates successful verification. The final synthesizer must qualify or withhold unsupported conclusions.

External fetching blocks private/local targets by policy and validates every redirect hop, timeout, byte size and content type. User-owned source files cannot leak into global memory. Exports and citations are authorized artifact access and audited.

---

## 14. API contract and client surface

### 14.1 Versioning

Introduce a versioned API such as /api/v1; current /api routes may remain local-only adapters during migration, but must invoke the same application services and policy. Each public request/response has Pydantic schema, stable IDs/timestamps and a documented error envelope with machine code, safe detail, correlation ID and retryability.

Bound request size, pagination, field lengths, query cost, tool output and artifact payload before expensive work. Use cursor pagination for high-volume records/events and bind cursors to authorized scope.

### 14.2 API groups

| Group | Operations | Security invariant |
|---|---|---|
| auth/session | sign-in, logout, rotation, revoke, current Principal | no secrets in URLs/logs |
| tenants/memberships | tenant select, membership/grants | current server membership is authority |
| workspaces | authorized list/select/configure | path is not ownership |
| agents | list/show/generate/validate/save/version/revert | profile cannot self-grant |
| providers | catalog/model capabilities/connection/credential references | scoped secret use |
| runs/tasks | create/show/list/cancel/pause/resume/retry and DAG | owner policy for every operation |
| events | subscribe/replay/resync | verify run before replay |
| tools/MCP | catalog/config/validation/calls | capability policy per invocation |
| artifacts | list/download/export/restore/delete | grant + containment + quotas |
| memory | search/store/inspect/forget/export | owner/scope filters before retrieval |
| research | source/claim/evidence/verify/export | provenance and source policy |
| audit/usage | query, budgets and usage | tenant/admin policy and redaction |
| health/ops | liveness/readiness/metrics | no host secrets or private tenant data |

### 14.3 Cross-client schema discipline

- Treat OpenAPI as a versioned artifact.
- Generate TypeScript client models and verify generated output in CI.
- Use explicit stable resource IDs and ISO timestamps.
- Use idempotency keys for run creation and other retryable mutations.
- Normalize validation/not-found/forbidden/conflict/rate-limit/timeout/cancel errors.
- Do not return host absolute paths in shared responses.
- Add tests comparing FastAPI/OpenAPI responses, TypeScript generated types and Rust serde structs.
- Native IPC may use JSON-RPC/stdio, but methods/events map to the same versioned application contract.

---

## 15. Browser UI, CLI/TUI and desktop

### 15.1 Browser vertical slice

Build a TypeScript client incrementally after the API/run/event ownership model stabilizes.

Minimum sequence:
1. sign in/select tenant/workspace;
2. create or select run with workflow, depth, budget and pinned agents;
3. show validated planning/proposed roles where policy requires it;
4. render real DAG, dependencies, workers, retries, cancellation and budget consumption;
5. stream durable events and reconnect with a replay cursor;
6. inspect tool summaries, policy/approval decisions, evidence and artifacts;
7. configure/reuse agents with validation/provenance;
8. configure providers without returning existing secret values;
9. inspect authorized memory/audit/usage and manage deletion/export;
10. show final verification status separately from worker completion.

On reconnect, load a durable run snapshot then replay after the last sequence. A cursor gap triggers resync. UI optimism may show a pending request, but it must not claim cancellation succeeded until the server confirms it.

### 15.2 Python CLI/TUI

Keep the Python CLI as a supported path during migration. Commands must use application services or an authorized API/IPC adapter and must not bypass ownership. Share IDs, lifecycle, budgets, error semantics, resume and event behavior.

### 15.3 Rust clients

The existing Rust clients handle rendering, keyboard/terminal lifecycle, desktop windowing, OS integration and strict DTO decoding. They should restore canonical state on restart, handle unknown incompatible schema versions safely and avoid plain-text long-lived cloud tokens. They must not duplicate task/run policy or provider routing.

Do not deprecate the Python CLI simply because a Rust binary exists. Require feature parity, installation/upgrade compatibility, platform testing and release notes first. Keep eframe desktop unless an ADR with UX/accessibility/distribution/security evidence warrants a different shell.

### 15.4 Client parity matrix

Each major capability must be tested through the intended API and supported clients:
- create/inspect/cancel/resume/reconnect a run;
- view dependencies, task state and real worker events;
- generate/validate/save an agent;
- inspect approvals and denied operations;
- view/download authorized artifacts;
- search/forget authorized memory;
- inspect research evidence/verification;
- choose model/provider within policy;
- recover from disconnect, expired session, provider failure, quota exhaustion and worker crash.

A UI button is not a working feature until service, ownership and tests exist.

---

## 16. Observability, quotas and recovery

### 16.1 Structured observability

Use structured redacted logs and stable request/run/task/execution/correlation IDs. Never log tokens, provider keys, session secrets or unrestricted tool payloads. Prompt/output text may contain user data; retention must follow explicit policy.

Instrument API, DB transactions, provider calls, tools, dispatch, workers and run lifecycle with OpenTelemetry incrementally. Personal mode must work without an external telemetry system. Reference: https://opentelemetry.io/docs/languages/python/instrumentation/

Track:
- active/queued/running runs and worker saturation;
- task duration, failure/retry rate and budget exhaustion;
- time-to-first-event and replay failure;
- provider latency/timeouts/rate limits/fallback;
- tool duration, output size, approval/denial and resource limit events;
- token/cost spending;
- DB pool saturation, transaction duration and lease recovery;
- artifact/memory storage and quota rejections;
- fairness/starvation;
- memory query latency and denied scope violations.

Avoid high-cardinality or sensitive labels in metrics; detailed identifiers belong in access-controlled traces/logs.

### 16.2 Quotas and fairness

Bound concurrency, agent count, delegation depth, wall-clock runtime, tokens/cost, provider rate, tool calls, subprocess CPU/memory/time/output, artifact bytes/count, source collection bytes/count, memory volume, event retention and simultaneous streams. Configuration cannot exceed a server-enforced ceiling. Update budget consumption atomically. Avoid letting one tenant monopolize workers.

### 16.3 Health and recovery

Liveness says the process responds. Readiness says critical dependencies/configuration work. Neither exposes secrets.

Test: restart with active durable state, worker crash/lease recovery, cancellation/shutdown and child cleanup, database outage/recovery, interrupted migration, backup/restore, provider outage/retry exhaustion, missing/corrupt artifact, event replay, disk full, permission denial and quota exhaustion.

---

## 17. Sequential qualification gates

The following expands existing ROADMAP.md gate numbering; it is not a competing gate system. A gate passes only when evidence is linked to the exact commit and required workflows have fully completed.

### Gate 1 — Repository and governance baseline

1. Reconcile master/main using ordinary merges only; never rewrite shared history.
2. Read back the actual GitHub default branch and protection/rulesets after authorized administrator changes.
3. Confirm workflow triggers, required check names, current-head status and PR target policy.
4. Inventory code/spec/tests and distinguish observed implementation from intended target.
5. Add supersession notices to stale contradictory docs; preserve history rather than silently deleting useful context.
6. Run current CI/Security against the exact candidate head.
7. Review dependency update PRs individually, including lock/build/test effects; do not merge batches only because checks pass on independent heads.

**Exit evidence:** verified GitHub settings and refs, current dependency/security baseline, source/spec/test map, exact CI evidence and named remaining blockers.

### Gate 2 — Multi-user identity and isolation

1. Version Principal, Tenant, membership, workspace grant and session contracts.
2. Implement local bootstrap and a provider-neutral identity integration.
3. Implement session expiry/revocation/rotation and authentication dependencies.
4. Add centralized policy and action/resource vocabulary.
5. Add tenant-aware relational schema, owner constraints, indexes and repository predicates.
6. Replace global mutable workspace/provider/session assumptions with request/run-scoped context.
7. Namespace credential references and enforce grants.
8. Scope sessions, runs/tasks, team messages, artifacts, memory, audit and event replay.
9. Propagate/revalidate Principal and authorization context through workers and tool calls.
10. Test cross-tenant access, revocation, migration, restore and concurrent users.
11. Keep non-loopback binding disabled until every proof obligation passes.

**Exit evidence:** complete adversarial denial matrix, migration/recovery evidence, strict lint/type checks, supported OS/Python matrix and exact CI/Security pass. A contract document or login UI does not pass Gate 2.

### Gate 3 — Shared runtime and contracts

1. Version API/error/event DTOs.
2. Add /api/v1 and define legacy adapters.
3. Implement durable run/task repository and transactional outbox.
4. Add idempotency and conditional transitions.
5. Persist event sequence/replay and authorized reconnect.
6. Define cancellation/resume/retry semantics and worker bounds.
7. Generate TypeScript and Rust DTOs from canonical schema where feasible.
8. Add schema/replay compatibility tests and crash/restart tests.
9. Verify API, CLI and IPC invoke the same application use cases.

**Exit evidence:** run survives/reconciles restart, events replay coherently, duplicate requests are safe and clients share lifecycle/error contracts.

### Gate 4 — Agents, tools and orchestration

1. Version profile schema/provenance and capability requests.
2. Enforce effective permissions separately from profile.
3. Implement bounded planning and validated DAG.
4. Enforce concurrency/depth/time/retry/tool/token/cost/artifact caps.
5. Isolate per-run planner/provider/workspace/cancellation context.
6. Authorize every tool/MCP invocation.
7. Qualify OS sandbox capabilities for the threat model.
8. Harden paths, shell/process, URL redirects, outputs and secret redaction.
9. Test worker retry, pause/resume/stop, cycles, duplicate dispatch and failure.
10. Verify the UI shows actual runtime events.

**Exit evidence:** adversarial policy tests, worker isolation, cancellation/resource exhaustion tests and real end-to-end runs.

### Gate 5 — Research, memory and persistence

1. Define scope ownership and memory repository contracts.
2. Filter sources before retrieval/ranking/prompt assembly.
3. Scope research sources/claims/evidence by tenant/run.
4. Preserve hard source/collection/depth semantics.
5. Invalidate verification after evidence changes.
6. Test time/saturation/continuous stops under slow/failing sources.
7. Test concurrent persistence, transactions, migration and restart.
8. Test retention, deletion, backup/restore, secret rotation and audit redaction.
9. Benchmark search backend before adding infrastructure.

**Exit evidence:** no cross-tenant retrieval/citation leakage, reproducible evidence tests and migration/recovery proof.

### Gate 6 — Client and end-to-end qualification

1. Complete an API/CLI vertical slice for runs/events/cancellation/artifacts.
2. Add typed TypeScript client and real workflow graph.
3. Align Rust clients to run/event contracts.
4. Add expiry/reconnect/cursor-gap/quota behavior to each client.
5. Qualify accessibility, keyboard handling and failure UI.
6. Prove local mode works without hosted identity and shared mode denies missing/expired auth.
7. Ensure policy and orchestration remain in the shared Python service.

**Exit evidence:** same run controllable through supported clients with matching durable state and ownership enforcement.

### Gate 7 — Release and operational qualification

1. Complete supported Python versions and Ubuntu/Windows/macOS test matrix.
2. Pass Ruff, formatting, configured strict MyPy and Rust format/compile.
3. Pass CodeQL, dependency audit, version contract and evidence generation.
4. Build/install from clean environments.
5. Test onboarding, upgrade, configuration/data migration and recovery.
6. Verify license notices, SBOM/provenance/signing if enabled and dependency exceptions.
7. Verify all required CI/Security checks passed on the exact tagged SHA.
8. Verify tag ancestry and actual GitHub settings.
9. Publish changelog, supported platforms, migration notes and limitations.
10. Update version metadata only after qualification; do not call the project production-ready while a gate is open.

---

## 18. Test plan by layer

### 18.1 Unit

Principal/policy matrix; membership revocation; legal state transitions; idempotency hash mismatch; cycle/unknown dependency; budgets/retry classification; provider fallback; path/symlink containment; secret redaction; memory scope derivation; event schema/ordering; source snapshot/quote verification; research stop conditions.

### 18.2 Repository/service integration

Two tenants with the same process; tenant query predicates; constraints/foreign keys; concurrent state transitions; duplicate outbox dispatch and lease recovery; transaction rollback; artifact metadata/content ownership; provider secret create/use/rotate/revoke; memory search/forget; membership revoked during worker activity; repeatable migration.

### 18.3 API/security

Missing/expired/revoked/malformed sessions; same-loopback request without auth in shared mode; tenant ID/header/body override; guessed IDs; unauthorized export/download/replay; CSRF/foreign origin; proxy/header spoofing; payload limits/rate limits; secret leakage scan; login rate limiting/session rotation; concurrent workspace changes.

### 18.4 Tool adversarial

Prompt injection asks to reveal secrets; profile asks for ungranted tools; arguments change after approval; path traversal/symlink race; malicious child processes/resource exhaustion; redirects to private targets; MCP injection/oversized payload; cancellation/orphan cleanup; cross-tenant artifact/memory/provider read; duplicate of non-idempotent side effect.

### 18.5 End-to-end/performance

Single-agent prompt-to-artifact; dependency-aware team with independent review; evidence-first research; reconnect after restart; large artifact tree with bounded memory and preserved response semantics; worker crash/cancel; two-tenant concurrent usage without event/data crossover; quota fairness; local CPU/model and hosted provider test environments.

Performance goals must follow reproducible benchmarks with hardware, model, provider, dataset, warm/cold distinction, percentile latencies and memory. Do not turn historical latency claims into acceptance promises without measurement.

---

## 19. Engineering workflow and definition of done

Each PR must start from the inspected current target branch, identify root cause, include regression tests, preserve or deliberately revise behavior, update canonical specs/docs, and run the full required workflows on its latest head. Do not merge queued, stale or unexpectedly skipped checks. Close duplicate PRs only after identifying the correct tested patch. Preserve shared history.

For local iteration, keep this list synchronized with .github/workflows/ci.yml:

    python -m pytest tests/ -q
    python -m ruff check src/
    python -m ruff format --check src/
    python scripts/check_version.py
    cargo fmt --manifest-path nexus-rs/Cargo.toml -- --check
    cargo check --manifest-path nexus-rs/Cargo.toml
    cargo fmt --manifest-path nexus-desktop/Cargo.toml -- --check
    cargo check --manifest-path nexus-desktop/Cargo.toml

Run the exact configured strict MyPy command from CI; do not claim it covers the entire tree if it currently targets selected modules. Expand strict coverage incrementally.

A task is done only when acceptance criteria pass; implementation is wired into a real code path; success/failure/security/compatibility tests exist; exact-head CI/Security finish green; relevant docs are updated; remaining risks and untested cases are honest; duplicate paths are accounted for; and integration follows repository policy. Multi-tenant security needs an attack-oriented proof matrix, not just unit tests or a green CodeQL run.

---

## 20. Required architecture decision records

Record context, alternatives, decision, consequences, migration and acceptance tests for:
1. identity provider and supported OIDC/CLI login flows;
2. shared database and SQLAlchemy/Alembic migration plan;
3. worker deployment, leases, queue and cancellation guarantees;
4. run/event schema versioning, retention and replay;
5. artifact storage: local filesystem versus object storage;
6. credential backend, key rotation and sharing grants;
7. OS sandbox guarantee per platform;
8. browser frontend framework/client generation;
9. native IPC versus HTTP and schema mapping;
10. memory retrieval backend and benchmark threshold;
11. audit/retention/redaction/deletion policy;
12. SBOM/provenance/signing and dependency-exception lifecycle.

These decisions should not block foundational work that is independent of the choice, but implementations must not silently diverge while the ADR remains unresolved.

---

## 21. Prohibited shortcuts

- Treat loopback, IP allowlists, CORS, Origin or TLS proxy as user authentication.
- Enable remote bind before full Gate 2 passes.
- Trust user_id, tenant_id, workspace_id, owner or role from request payload/header.
- Rely on non-guessable IDs instead of ownership predicates.
- Use global active session/provider/workspace for concurrent Principals.
- Filter memory only after retrieval/ranking/prompt construction.
- Give workers blanket global provider credentials, filesystem roots or event queues.
- Let a model or profile grant itself capabilities.
- Spawn unbounded agents, replan indefinitely or retry all failures.
- Send secrets in URLs, prompts, logs, events, agent profiles or ordinary config responses.
- Claim OS sandbox based solely on shell=False, path checks or timeout.
- Render simulated workflow progress as runtime truth.
- Let a client bypass a shared service to manipulate domain state.
- Move orchestration into Rust without measured benefit and contract proof.
- Maintain divergent implementations of task lifecycle or provider routing.
- Accept checks from an old SHA as proof for a changed head.
- Treat branch-governance documentation/advisory as proof that GitHub settings are enforced.
- Force-push or delete refs to hide divergence.
- Call an alpha build or a design document production ready.

---

## 22. Open choices and defaults

| Decision still open | Recommended default | Work that can proceed now |
|---|---|---|
| Identity provider | Provider-neutral OIDC adapter with local bootstrap; choose concrete provider against self-hosting needs | Principal/session/policy model and tests |
| Tenant meaning | Personal installation is a personal tenant; teams/orgs are separate tenants | Schema and membership contracts |
| Shared database | PostgreSQL; SQLite for local mode | Repositories, migrations and local tests |
| Job dispatch | Database outbox/leases with bounded worker first | Durable run/task model |
| Browser framework | React + TypeScript + Vite for new rich views, incremental migration | API schema and generated types |
| Artifact backend | Authorized local filesystem first; optional object storage behind an interface | Ownership-aware manifest/containment |
| Shared secret backend | Pluggable encrypted backend with rotation; current local adapter retained | Secret refs and authorization |
| OS isolation | Platform-specific documented guarantees, stronger isolation for untrusted code where available | Capability model and sandbox tests |
| Memory search | Current SQLite FTS locally, shared search selected after benchmark | Scope ownership and repository contract |
| Desktop shell | Keep current eframe client until an ADR justifies a change | API/event parity |
| Remote access | Disabled until Gate 2 passes | Build/test shared mode without opening it |

---

## 23. Priority order: next implementation work

**First: repository governance.** Finish the live master/main reconciliation with normal PR merges, then have an authorized administrator change/read back default-branch and protection settings. Content synchronization is not a settings migration.

**Second: Gate 2 identity and tenant-owned data plane.** Implement Principal/session, memberships/workspace grants, central policy, ownership-aware repositories, local bootstrap, credential references, run-scoped worker context and attack-oriented denial tests. Keep remote binding disabled.

**Third: durable runtime contracts.** Implement run/task/event schema, idempotent dispatch, conditional transitions and replay. Remove global mutable workspace/provider/session assumptions from execution paths while preserving local mode.

**Fourth: tool/MCP policy and sandbox.** Centralize invocation authorization and add truthful platform isolation with resource limits.

**Fifth: memory, research and artifact ownership.** Apply tenant filters before retrieval and evidence construction; qualify retention, migrations and replay.

**Sixth: client experience and parity.** Build the TypeScript workflow console and make Python/Rust clients consume the same contracts. Do not duplicate execution logic.

**Seventh: release/operations qualification.** Complete cross-platform end-to-end, recovery, quota, security and release evidence. Consider service separation or Rust-side runtime work only if measured needs justify it.

This ordering is deliberate: better UI cannot compensate for an unauthenticated data plane, and more agents cannot compensate for unbounded execution or ambiguous ownership.

---

## 24. References and document precedence

Framework references:
- Python asyncio: https://docs.python.org/3/library/asyncio.html
- FastAPI security: https://fastapi.tiangolo.com/tutorial/security/
- SQLAlchemy ORM: https://docs.sqlalchemy.org/en/20/orm/
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- Alembic migrations: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- React: https://react.dev/
- TypeScript: https://www.typescriptlang.org/docs/
- Vite: https://vite.dev/guide/
- Tauri architecture, reference only and not a decision to replace the current desktop shell: https://github.com/tauri-apps/tauri-docs/blob/v2/src/content/docs/concept/architecture.mdx
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- MCP SDK: https://modelcontextprotocol.io/docs/sdk

Repository sources of requirements:
- README.md — product scope, clients and language decision.
- docs/ARCHITECTURE.md — authoritative architecture and language allocation.
- docs/MULTI_AGENT_PLATFORM.md — multi-agent platform contracts.
- docs/ORCHESTRATION.md — scheduling, budgets, lifecycle and research behavior.
- docs/STORAGE_AND_GOVERNANCE.md — storage, credentials and Gate 2 Principal/tenant contract.
- docs/ROADMAP.md — sequential qualification gates.
- docs/SECURITY.md — current security claims and limitations.
- docs/API.md — current API and local-only binding constraints.

When an implementation decision changes, update the relevant canonical document and record exact code commit, tests/workflow links, limitations, migration consequences and owner of unresolved risk. Do not mark an item complete merely because code was added or merged.
