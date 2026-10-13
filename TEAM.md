# NexusAgent Team Operating Model

> Normative collaboration and execution guidance for human developers and AI coding agents.

## Mission

Deliver a real, secure, provider-agnostic multi-agent platform through small, coherent, evidence-backed changes. Research, coding, review, planning and automation are workloads of one platform, not separate products.

## Roles and order of responsibility

1. **Requester / product owner:** defines goals, constraints and approval boundaries.
2. **Orchestrator / planner:** decomposes work, defines acceptance criteria and dependencies, selects existing profiles and identifies capability gaps.
3. **Domain specialist:** investigates or implements the assigned bounded task and records evidence.
4. **Independent verifier:** checks claims against source, tests, outputs and acceptance criteria; does not merely repeat the implementer's summary.
5. **Integrator / release owner:** resolves cross-component compatibility, executes validation, updates documentation and prepares the governed merge.
6. **Final synthesizer:** communicates changes, evidence, remaining risks and exact delivery state.

One agent may cover multiple roles for small tasks, but implementation and independent verification must remain logically distinct for high-risk changes.

## Task contract

Every non-trivial task identifies:
- goal and user-visible deliverables;
- scope and explicit exclusions;
- dependencies and files/interfaces affected;
- acceptance criteria and failure cases;
- required tools and permissions;
- validation commands or GitHub workflows;
- expected artifacts and handoff recipient.

## Collaboration rules

- Reuse a valid existing profile when suitable; generate a new profile only for a distinct capability or accountability gap.
- Give each worker a bounded assignment and explicit output contract.
- Parallelize independent tasks only; serialize conflicting writes and integration-sensitive changes.
- Exchange structured findings, artifacts and evidence references, not only free-form status messages.
- The verifier inspects the actual changed code and test output.
- Stop at an authorization boundary or unresolved product decision; never bypass it through generated instructions.
- Bound agent count, recursion, retries, token/time budgets and re-planning.
- Cancellation and failure propagate to dependent tasks and remain visible to the requester.

## Repository engineering protocol

1. Read this file, AGENTS.md, docs/PRODUCT_SPECIFICATION.md and relevant component documentation.
2. Inspect the live repository and current GitHub state before relying on historical notes.
3. Treat code, tests and current workflow results as implementation evidence; treat specs as intended behavior.
4. Preserve history. Never force-push or rewrite shared history. Do not commit unrelated changes.
5. Use a coherent branch and pull request targeting the canonical integration branch unless live repository policy explicitly requires another workflow.
6. Run focused tests, then the full relevant suite and required quality/security checks.
7. Fix failures caused by the change; never weaken gates merely to obtain green status.
8. Update specs, architecture, operational docs and changelog when behavior or decisions change.
9. Confirm exact commit, CI/security outcomes and merge state before claiming delivery.

## Handoff format

A completed handoff states: files/areas changed; design decisions; exact validation and results; CI run/commit references; known failures or blockers; security/persistence implications; docs updated; next action. Never claim a test, push, merge, protection rule or release occurred without direct evidence.
