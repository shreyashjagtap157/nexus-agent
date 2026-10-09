# NexusAgent Project Context

> Last reviewed: 2026-10-09
> Current version: 0.3.0-alpha.5 (unreleased)
> Canonical branch: main

This file is a concise handoff index. The full implementation backlog, architecture workstreams, test strategy, deployment procedure and qualification checklist live in [PROJECT_COMPLETION_AND_QUALIFICATION.md](PROJECT_COMPLETION_AND_QUALIFICATION.md). Do not use old phase estimates or legacy claims as evidence of current completion.

## Product

NexusAgent is a local-first development and research workbench built around a shared Python runtime. Supported product surfaces include a CLI/TUI, FastAPI web UI, native Rust CLI and native desktop application. The platform includes local/hosted LLM providers, tools, memory, sessions, skills, MCP, saved/generated agents, multi-agent teams and source/claim-oriented research.

## Repository map

| Area | Primary location |
| --- | --- |
| Agent loop/orchestration | src/nexus_agent/core/ |
| Providers/local inference | src/nexus_agent/llm/ |
| Tools and capabilities | src/nexus_agent/tools/ |
| Team planning/runtime/state | src/nexus_agent/team/ |
| Research sources/claims/quality | src/nexus_agent/research/ |
| Memory and sessions | src/nexus_agent/memory/, src/nexus_agent/session/ |
| Configuration, permissions and persistence | src/nexus_agent/core/config.py, src/nexus_agent/permissions/, src/nexus_agent/storage/ |
| HTTP/MCP | src/nexus_agent/*/web_routes.py, src/nexus_agent/mcp/ |
| Native CLI | nexus-rs/ |
| Native desktop | nexus-desktop/ |
| Tests | tests/ |
| CI, Security and Release | .github/workflows/ |

## Development setup

    python -m venv .venv
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python -m pip check
    nexus --version
    nexus hardware

Activate the virtual environment before installing. Use optional extras only for the feature/platform being tested.

## Local qualification commands

    python -m compileall -q src
    python -m pytest tests/ -q --tb=short -W error::ResourceWarning
    python -m ruff check src/
    python -m ruff format --check src/
    python scripts/check_version.py
    cargo fmt --manifest-path nexus-rs/Cargo.toml -- --check
    cargo check --manifest-path nexus-rs/Cargo.toml
    cargo fmt --manifest-path nexus-desktop/Cargo.toml -- --check
    cargo check --manifest-path nexus-desktop/Cargo.toml

Use the exact MyPy command in .github/workflows/ci.yml for CI parity. The release workflow may check a broader source scope; any difference is tracked as a qualification gap.

## Engineering rules

- Inspect the live repository, current tests, workflow definitions and current-head workflow results before choosing work.
- Make a coherent change in the owning layer and identify all affected callers/integrations.
- Add a regression test for every bug fix. Security tests must assert no side effects, not just an error message.
- Keep tool permissions action-aware, path/network/subprocess boundaries bounded and fail closed.
- Treat model output, fetched content, agent profiles and MCP payloads as untrusted.
- Use migrations for persistence changes and test upgrade/recovery behavior.
- Update the relevant architecture/API/security/versioning document and CHANGELOG.md when public behavior changes.
- Never force-push, rewrite published tags, weaken tests to produce a green check, or treat queued/skipped/cancelled runs as success.

## Current qualification posture

Alpha.5 is not a 1.0 release. The latest observed CI/Security workflows on the recorded main snapshot passed, but GitHub administration still needs to make main the default and protect it. The narrow dependency-audit exception and CI-versus-release type-check scope are tracked explicitly in the completion guide; review them using fresh evidence before release promotion.
