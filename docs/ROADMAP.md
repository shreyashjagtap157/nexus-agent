# NexusAgent Execution Roadmap

> Current baseline: 0.3.0-alpha.5
> Status: active hardening and release qualification
> Canonical integration branch: main

This roadmap is the short prioritization view. The detailed implementation, testing, deployment and release acceptance contract is maintained in [PROJECT_COMPLETION_AND_QUALIFICATION.md](PROJECT_COMPLETION_AND_QUALIFICATION.md). Historical estimates are not current implementation evidence.

## Current product baseline

NexusAgent provides a shared Python agent runtime with CLI/TUI and FastAPI surfaces, native Rust CLI and desktop clients, local and hosted provider integrations, tool execution, scoped memory, sessions, MCP, generated/saved agents, team orchestration and evidence-oriented research. Cross-surface behavior and security must be qualified by current tests rather than inferred from the presence of a module.

## Priority order

### P0 — Release-blocking foundations

1. Set main as the GitHub default branch and apply real branch protection/rulesets; issue #326 records the administrator action. Documentation alone does not satisfy this gate.
2. Keep CI / Required and Security / Required green on the exact candidate commit.
3. Reassess the narrowly scoped diskcache dependency-audit exception when upstream/dependency evidence changes.
4. Reconcile the critical-module MyPy list in normal CI with the broader check performed by the release workflow; grow coverage rather than hiding failures.
5. Correct stale continuation/implementation documentation and make installation, API, migration, backup and rollback instructions match actual behavior.

### P1 — Correctness and end-to-end qualification

1. Expand full-tree type checking and shared CLI/web/MCP/native contract tests.
2. Complete multi-process persistence, migration, backup/restore and crash-recovery qualification.
3. Test provider retry, timeout, cancellation and fallback identity under fault injection.
4. Exercise team scheduling, lifecycle control, worker-local permissions and resource budgets under randomized DAGs and concurrent load.
5. Qualify evidence changes, stale research verification, source provenance, source deduplication and SSRF boundaries end to end.
6. Smoke-test built packages and native artifacts in clean environments on every claimed platform.
7. Improve redacted diagnostics, support matrix, resource metrics and troubleshooting flows.

### P2 — After correctness stabilizes

1. Improve accessibility, UX consistency and setup friction.
2. Optimize performance only after establishing reproducible baselines.
3. Add providers, backends or tools only for documented user needs with shared contract, security and cross-surface tests.
4. Do not expose remote/shared deployment until authentication, tenant isolation and operational controls are separately designed and reviewed.

## Qualification rule

A phase is complete only when its acceptance criteria can be traced to actual tests, workflow URLs, artifact inspection or verified GitHub settings. A queued, cancelled, skipped or stale-head workflow is not a pass. Do not promote directly from alpha to 1.0 merely because a workflow is green.

## Historical material

Older audit and implementation documents remain as historical reference. Their snapshots, estimates, file counts and feature-status assertions must not override current main, current tests or the detailed completion guide.

