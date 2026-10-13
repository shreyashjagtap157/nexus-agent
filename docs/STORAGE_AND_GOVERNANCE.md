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


## Tenant-aware storage requirements (2026-10-13)

Local/personal and authenticated multi-user operation are both initial requirements. Storage design must make ownership explicit for users, tenants, workspaces, sessions, runs, task graphs, messages, events, artifacts, memory and provider credential references.

- Enforce ownership in the service/data-access layer for every lookup and mutation; random or guessed IDs are not authorization.
- Use transaction boundaries and concurrency control appropriate for simultaneous users and workers. SQLite may remain suitable for local mode, but multi-user deployment must not assume that a single-user SQLite file is a sufficient shared production database without validated concurrency, migration, backup and recovery behavior.
- Partition memory by declared scope (global, user, workspace, project and session) and reject unauthorized cross-scope access.
- Apply per-tenant limits for concurrent tasks, storage, artifacts, provider spend and tool runtime.
- Keep secrets outside ordinary configuration and artifacts; use tenant-scoped secret references and safe rotation/revocation.
- Record auditable mutations without storing secrets or unrestricted prompt/tool payloads by default.
- Test concurrent writes, interrupted transactions, cancellation, migration, backup/restore and tenant isolation with negative tests.
