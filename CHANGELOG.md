# Changelog

All notable NexusAgent changes are recorded here.

Release precedence and compatibility are governed by Semantic Versioning.

## [Unreleased]

Future changes not yet assigned to a release.

## [0.3.0-alpha.1]

### Added

- Unified local multi-agent runtime architecture.
- Dynamic professional team generation and reusable user/project/workspace/global agent profiles.
- Persistent team blackboard, dependency-aware scheduling, lifecycle controls and telemetry.
- Scoped memory across global, user, project, workspace, agent, team and session boundaries.
- Evidence-first research tooling and a 21-level research-depth policy.
- Provider credential store, common OpenAI-compatible provider catalog and NVIDIA NIM routing.
- Reversible file deletion, move/rename, structured-data parsing and a unified tool catalog.
- Web Team Console and Agent Forge surfaces.
- CLI, native Rust CLI/TUI and native desktop controls for team execution.

### Changed

- Product version moved to the 0.3.0-alpha.1 development line because the multi-agent workbench changes the public architecture and expands the compatibility surface.
- The release gate now verifies every runtime/client manifest plus both Rust lockfile/package versions.

### Release status

This is an alpha development release. The public API, team protocol, provider schema, tool contracts and storage layout remain provisional until 1.0.0.


### Added

- Unified local multi-agent runtime architecture.
- Dynamic professional team generation and saved agent profiles.
- Persistent team blackboard, lifecycle controls and telemetry.
- Scoped memory and canonical runtime storage layout.
- Evidence-first research tooling and 21-level research-depth policy.
- Provider credential store and extensible provider catalog.
- NVIDIA NIM / Nemotron 3.5 Lightning routing support.
- Web Team Console and Agent Forge surfaces.
- CLI and native client team execution controls.

## [0.2.0-alpha.1]

Initial multi-agent platform prerelease baseline.

This prerelease establishes the unified product architecture and is not a stable compatibility commitment.
