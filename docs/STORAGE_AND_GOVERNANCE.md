# NexusAgent Storage and File Governance

NexusAgent deliberately separates user state, project-shareable configuration and transient runtime data.

## Canonical scopes

Global data uses the operating-system global data directory.

User data uses the NexusAgent user data directory, typically ~/.nexus-agent on Unix-like systems.

Project data is rooted at the project root. Project agent definitions are intended to be version-controlled.

Workspace-local overrides are rooted at .nexus-agent.

Runtime state is rooted at .nexus-agent/runtime.

## Runtime isolation

.nexus-agent/.gitignore keeps runtime databases, memory, logs, caches and trash out of source control while allowing agent definitions to remain version-controlled.

The file journal records high-level mutations with previous/new hashes where applicable. It is audit telemetry, not a replacement for Git.

## File operations

write_file writes atomically.

delete_file moves files into runtime trash unless permanent=true is explicitly requested.

restore_file restores a trash entry to a selected workspace destination.

move_file prevents path escape and destination collision.

parse_data parses JSON, YAML, TOML, CSV and XML with bounded output.

Agent file tools refuse .git mutation and reject workspace escapes.

## Credentials

Provider credentials are separate from normal project configuration. AuthStore uses an optional OS keychain when available and a permission-restricted file fallback otherwise.

Never commit API keys, OAuth tokens, passwords or other secrets.


## Memory Workbench

The local Memory Workbench at `/memory.html` exposes scoped persistent memory without requiring direct database manipulation. The same scopes are available through the scoped memory tool and web API.



## Gate 2 principal, tenant and session contract (proposed normative contract, 2026-10-13)

This section defines the ownership and authorization contract that must be implemented before authenticated multi-user exposure. It is a design target, not a claim that current runtime code already enforces these invariants. Existing local-only endpoints and filesystem scopes do not provide tenant identity.

### Identity and authorization model

- **User**: immutable server-generated `user_id`; represents a human or explicitly registered service actor. User-supplied display names and email addresses are attributes, never primary authorization identifiers.
- **Tenant**: immutable `tenant_id`; the top-level security and quota boundary. A tenant may represent a personal installation, a team, or an organization.
- **Membership**: a server-owned relation between `user_id`, `tenant_id`, and a role/status. Minimum roles are `owner`, `admin`, `member`, and `read_only`; action-level policy remains explicit and must not be inferred from role names alone.
- **Workspace**: immutable `workspace_id` owned by exactly one tenant. Membership and workspace grants decide which tenant users may act in a workspace. A filesystem path or workspace slug is a locator, not proof of ownership.
- **Principal**: a validated request context created only after session verification. It carries `user_id`, the selected `tenant_id`, `session_id`, authentication method, authorization version, issue/expiry times, and effective membership/role data. Do not accept these claims directly from request JSON, query parameters, arbitrary headers, or forwarded-IP headers.
- **Resource ownership**: each tenant-owned record carries `tenant_id`; resources requiring individual ownership also carry `owner_user_id`, and workspace-scoped records carry `workspace_id`. Shared resources require an explicit grant/visibility rule. Built-in immutable resources are the only implicit public scope.

Tenant selection must be derived from the verified session plus a current, server-side membership lookup. A caller changing a tenant ID, workspace ID, session/run ID, or artifact path must not change the caller's authority. Revoked memberships and changed role grants must take effect without trusting stale client-side claims.

### Request and service enforcement

1. The HTTP/API boundary resolves one validated principal through an authentication dependency. Missing, expired, revoked, malformed, or version-stale sessions fail closed for protected operations.
2. The policy layer authorizes an action against the target resource before reads, writes, lists, downloads, exports, streaming subscriptions, cancellation, resume, reconnect/replay, and deletion.
3. Service and data-access queries include the ownership predicates (tenant plus applicable owner/workspace/grant) in the query itself. Checking a path, a random-looking ID, or a peer address alone is insufficient.
4. Background jobs and team workers persist the originating actor, tenant, workspace, and authorization context. They must revalidate authority when starting, resuming, cancelling, accessing tools/secrets, and emitting events; a worker does not inherit blanket process-global access.
5. WebSocket/event delivery authorizes every session/run subscription and replay cursor. Never broadcast from process-global queues and rely on client filtering.
6. File/artifact operations resolve the selected workspace through an authorized workspace record, then enforce canonical path containment and symlink policy. User-controlled paths cannot select the tenant or bypass a database ownership check.
7. Audit events include actor, tenant, action, resource, outcome and correlation ID, while excluding raw credentials, bearer tokens, and unrestricted prompt/tool payloads by default.

### Session and browser security

- Session identifiers and bearer secrets are high-entropy opaque values; persist only a one-way verifier/digest where server-side revocation is required. Never place long-lived tokens in URLs, logs, event payloads, or generated agent profiles.
- Sessions have explicit creation, rotation, idle expiry, absolute expiry, revocation, logout and recovery semantics. Rotate session identifiers at authentication and privilege changes. Expiry and revocation are enforced server-side.
- Browser sessions use narrowly scoped cookies (`HttpOnly`, an explicit `SameSite` policy, `Secure` when served over HTTPS) and CSRF protection for state-changing requests. Enforce expected-origin checks for browser requests and WebSocket upgrades; CORS is not authentication or authorization.
- Password/SSO/bootstrap mechanisms must be versioned, use vetted password hashing or an established identity provider, limit login attempts, avoid user enumeration, support credential/session revocation, and never store raw passwords. Do not roll a custom cryptographic protocol.
- WebSocket authentication must reuse a verified session or a short-lived single-use connection ticket; do not accept an arbitrary session ID in the URL as identity.

### Local-mode bootstrap and compatibility migration

- Local/personal mode bootstraps an explicit single local principal and personal tenant, and routes through the same principal-aware services and ownership predicates as multi-user mode. Loopback is a deployment constraint, not the principal itself.
- Multi-user mode has no anonymous/local fallback. Missing authentication remains denied even when a request reaches a protected service from a loopback address.
- The migration from current per-user-machine stores creates a documented backup and a transactional, repeatable migration record. Existing local sessions, memory, agent definitions, audit entries, provider-secret references and artifacts are assigned to the explicitly approved local owner/tenant; never silently promote legacy data into a shared tenant.
- Migrations preserve stable resource IDs where possible, add explicit ownership foreign keys/indexes, verify row and artifact counts/hashes, and support rollback or documented recovery. Secret material remains in the credential store/keyring; only tenant-scoped secret references and access grants are persisted with ordinary domain records.
- The initial legacy migration is single-owner only. Importing existing state into a multi-user deployment requires an explicit owner/tenant selection and an auditable confirmation rather than automatic cross-tenant sharing.

### Gate 2 proof obligations

Before enabling non-loopback/shared deployment, add positive and negative tests that prove:

- User A cannot list, read, modify, delete, download, export, resume, cancel, subscribe to, or replay User B's sessions, runs, tasks, messages, research sources, team data, artifacts, scoped memory, agent profiles, audit events, or provider credentials—even when IDs are guessed.
- Tenant/workspace switching is authorized against current membership; revoked memberships and roles invalidate access; clients cannot override tenant identity through headers/body/path parameters.
- Cookies/tokens are not accepted cross-origin for state-changing browser operations; session expiry/revocation, logout, rotation, replay resistance and WebSocket origin/session checks work.
- Parallel users and workers cannot leak process-global context, provider selection, credentials, cancellation signals, events or workspace paths across tenants.
- Migration, concurrent writes, quota enforcement, interruption, backup/restore, secret rotation, deletion and audit-redaction cases pass on the supported OS/Python matrix.

The remote-bind guard is only an interim exposure mitigation. Gate 2 remains open until these invariants exist in implementation and are demonstrated on the exact candidate commit by tests and CI/Security evidence.

## Tenant-aware storage requirements (2026-10-13)

Local/personal and authenticated multi-user operation are both initial requirements. Storage design must make ownership explicit for users, tenants, workspaces, sessions, runs, task graphs, messages, events, artifacts, memory and provider credential references.

- Enforce ownership in the service/data-access layer for every lookup and mutation; random or guessed IDs are not authorization.
- Use transaction boundaries and concurrency control appropriate for simultaneous users and workers. SQLite may remain suitable for local mode, but multi-user deployment must not assume that a single-user SQLite file is a sufficient shared production database without validated concurrency, migration, backup and recovery behavior.
- Partition memory by declared scope (global, user, workspace, project and session) and reject unauthorized cross-scope access.
- Apply per-tenant limits for concurrent tasks, storage, artifacts, provider spend and tool runtime.
- Keep secrets outside ordinary configuration and artifacts; use tenant-scoped secret references and safe rotation/revocation.
- Record auditable mutations without storing secrets or unrestricted prompt/tool payloads by default.
- Test concurrent writes, interrupted transactions, cancellation, migration, backup/restore and tenant isolation with negative tests.
