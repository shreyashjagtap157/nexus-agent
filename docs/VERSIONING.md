# NexusAgent Versioning Policy

NexusAgent uses Semantic Versioning 2.0.0 syntax and immutable release tags.

## Canonical version

The repository-root `VERSION` file is the sole canonical release value.

These published artifacts MUST match it exactly:

- `pyproject.toml`
- `src/nexus_agent/__init__.py`
- `nexus-rs/Cargo.toml`
- `nexus-rs/Cargo.lock` package entry for `nexus`
- `nexus-desktop/Cargo.toml`
- `config/default.yaml`
- `src/nexus_agent/_default_config.yaml`

`python scripts/check_version.py` is the authoritative repository synchronization check.

## Development lifecycle

NexusAgent is currently pre-1.0.0. A pre-1.0 version explicitly means the public API and compatibility guarantees are not yet declared stable.

The normal release sequence for a feature line is:

`0.y.z-alpha.N` → `0.y.z-beta.N` → `0.y.z-rc.N` → `0.y.z`

An alpha is for active architectural and feature development. A beta is for stabilization and integration hardening. A release candidate is intended to contain only release-blocking fixes.

Prerelease identifiers are monotonic within their line. A published prerelease is never relabeled or reused.

## Pre-1.0 compatibility rules

For `0.y.z` releases, compatibility is provisional and the minor component may contain breaking public changes. NexusAgent documents those changes in the changelog and migration notes when they affect users.

Within one development line, the patch component is reserved for changes that do not intentionally alter the documented public contract.

This is deliberately stricter than the minimum SemVer rules for 0.x projects so that downstream users have a more predictable engineering signal.

## 1.0.0 and later

`1.0.0` is reserved for the point where the documented CLI, HTTP API, MCP/tool contracts, provider configuration, persistence formats, team protocol and native client/backend protocol have an explicit stability commitment.

After `1.0.0`:

- MAJOR = incompatible public changes.
- MINOR = backward-compatible functionality.
- PATCH = backward-compatible fixes.

## Enterprise release gates

A release is eligible only when all are satisfied:

1. The canonical version is valid SemVer.
2. Every required manifest and lockfile entry matches `VERSION`.
3. The complete test suite passes on the supported operating systems/Python versions.
4. Lint and type checks pass.
5. Native Rust/desktop checks pass.
6. Package/build metadata validation passes.
7. Security/dependency checks required for the release tier pass.
8. The changelog and any migration notes are updated.
9. The Git tag is exactly `v<version>`.
10. The tag and release are immutable after publication.

## Tag policy

Tags MUST use:

`v<version>`

Examples:

`v0.3.0-alpha.3`
`v0.3.0-beta.1`
`v0.3.0-rc.1`
`v0.3.0`
`v1.0.0`

Never force-push or rewrite a published tag.

## Current repository state

The current development snapshot is `0.3.0-alpha.3`. It is an unreleased prerelease and MUST NOT be represented as a stable `0.3.0` release or tag.
