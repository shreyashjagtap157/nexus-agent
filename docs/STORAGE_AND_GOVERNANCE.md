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
