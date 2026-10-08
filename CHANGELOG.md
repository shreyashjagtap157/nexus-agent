# Changelog

All notable NexusAgent changes are recorded here.

Release precedence and compatibility are governed by Semantic Versioning.

## [Unreleased]

Changes not yet assigned to a release.

## [0.3.0-alpha.3]

### Added

- Reusable agent profiles that can be authored manually or generated from natural-language requirements.
- Explicit global, user, project and workspace agent-definition scopes with deterministic precedence.
- Multi-agent team execution using dedicated AgentLoop workers, peer messaging, dependency-aware scheduling, persistent history and lifecycle control.
- Evidence-first research storage for source snapshots, claim quotations and deterministic quote-presence verification.
- Scoped memory across global, user, project, workspace, agent, team and session boundaries.
- Persistent chat/file/both output contracts with Markdown, text and JSON artifact generation.
- Extensible provider catalog, credential lifecycle and per-agent provider/model routing, including NVIDIA NIM.
- Expanded operational tools for filesystem mutation, reversible deletion, structured-data parsing, shell, Git, web, browser, code intelligence, LSP, MCP, memory and research.
- Web Team Console and Agent Forge interfaces plus native CLI/team controls.

### Changed

- Versioning now advances the canonical development snapshot to `0.3.0-alpha.3` across the Python package, runtime, Rust clients, default configuration and lockfile.
- NexusAgent is positioned as a general-purpose local multi-agent development and research workbench; research is a first-class workload rather than the sole product scope.
- Provider credentials are separated from normal project configuration, following the same architectural principle used by modern agent CLIs.

### Release status

Alpha.3 is an unreleased development snapshot. Public CLI, HTTP, MCP, tool, provider, storage and native protocol compatibility remain provisional.

## [0.3.0-alpha.2]

### Added

- Continued unified multi-agent runtime hardening.
- Persistent team lifecycle controls, history, telemetry and explicit output contracts.
- Provider/model routing and credential separation.
- Evidence-first research storage and canonical workspace runtime layout.
- Expanded filesystem, parsing, browser, code-intelligence and team-tool integration.

## [0.3.0-alpha.1]

### Added

- Initial unified local multi-agent runtime architecture.
- Dynamic professional role generation and persistent team blackboard.
- Scoped memory and research-depth policy.
- Provider catalog and NVIDIA NIM routing.
- Web Team Console, CLI and native team surfaces.

## [0.2.0-alpha.1]

Initial multi-agent platform prerelease baseline.

This prerelease established the unified product architecture and did not provide a stable compatibility commitment.
