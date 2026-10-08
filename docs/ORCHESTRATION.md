# NexusAgent Orchestration

Named workflows are first-class orchestration policies.

Built-in workflows:
- code-change
- build-review
- research-verify
- exhaustive-research
- architecture-debate
- repository-audit
- automation

A workflow establishes a baseline policy. Users can still override team size, parallelism, provider/model routing, output format, research depth and pinned agents.

## Dependency-aware scheduling

Independent agents run concurrently up to the configured parallelism. Dependent agents wait for prerequisites.

Unknown dependencies and dependency cycles become explicit failures rather than deadlocks.

## Coordination

Every worker receives team_send_message and team_read_messages.

The persistent team store records team configuration, role profiles, worker lifecycle, provider/model resolution, messages, events, failures and artifacts.

## Lifecycle

Teams can be paused, resumed and stopped. Control requests are persisted so a separate local client can control a running team.

## Research

Research workers can persist exact source snapshots, factual claims and supporting quotations. Deterministic verification checks that a recorded quotation is present verbatim in its stored source snapshot.

Research depth ranges from glance through maximal, with deeper levels increasing research expectations.
