# NexusAgent Versioning Policy

NexusAgent uses Semantic Versioning 2.0.0 for all public releases.

## Canonical version

The repository root \`VERSION\` file is the canonical release version.

The following artifacts MUST remain synchronized with it:

- \`pyproject.toml\`
- \`src/nexus_agent/__init__.py\`
- \`nexus-rs/Cargo.toml\`
- \`nexus-desktop/Cargo.toml\`

\`python scripts/check_version.py\` is the authoritative consistency check.

## Version states

### Development

While the public API is still evolving, use \`0.y.z\` versions. This follows SemVer's initial-development rule.

### Prerelease

Use:

- \`0.2.0-alpha.N\` for feature-complete development snapshots
- \`0.2.0-beta.N\` for stabilization and integration hardening
- \`0.2.0-rc.N\` for release candidates

Prereleases are ordered by SemVer precedence and MUST NOT be relabeled after publication.

### Stable

Use:

- \`0.2.0\` for a backward-compatible pre-1.0 release
- \`1.0.0\` when the documented public API, protocol, configuration, client behavior and compatibility guarantees are declared stable

After \`1.0.0\`:

- PATCH = backward-compatible fixes
- MINOR = backward-compatible features
- MAJOR = breaking public API/protocol behavior

## Release tags

Tags MUST use:

\`v<version>\`

Examples:

\`v0.2.0-alpha.1\`

\`v0.2.0\`

Never reuse a published tag and never modify an immutable release.

## Compatibility surface

Before 1.0.0, compatibility is explicitly provisional, but releases still document breaking changes.

The protected public compatibility surface includes:

- CLI command names/options
- team/workflow configuration schema
- agent profile format
- MCP/tool contracts
- provider configuration and credential behavior
- HTTP API routes and request/response schemas
- native client/backend protocol
- persisted team/session schema migrations
- artifact and storage layout where documented as durable

## Release gates

A release requires:

1. version synchronization check
2. full test suite
3. lint and type checks
4. native Rust checks
5. package build and metadata validation
6. dependency/security audit appropriate to the release
7. changelog entry
8. immutable Git tag matching \`VERSION\`

Release automation rejects a tag whose name does not exactly match the canonical version.
