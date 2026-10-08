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

Research depth ranges from glance through maximal. The post-deployment coordination protocol
is bounded to 5–10 dependency-aware waves. Deeper levels increase sources per wave,
independent verification passes, contradiction analysis, formal-analysis passes,
review passes and minimum independent-source thresholds.

Planning is a one-time team-deployment phase. Once workers are deployed, they execute
their missions through the shared blackboard and move to final review rather than
recursively regenerating the team.


## Fail-closed scheduling and evidence boundaries

The scheduler validates unknown dependencies before building each ready wave. A worker with an unknown prerequisite is persisted as failed and is never submitted to the executor; dependency cycles are likewise surfaced explicitly rather than spinning.

Research source policy is enforced before worker tool construction. In `user_only` mode, workers can fetch only sources explicitly registered in the workspace research-source registry. Generic source capture is available only for `hybrid` and `autonomous` modes, and it fetches the URL itself before the evidence snapshot is persisted.

Dynamic worker tools are permission-checked against the actual worker-local tool catalog. This prevents dynamically added research, MCP or skill tools from being misclassified because they are absent from the parent runtime's original tool list.

Provider routing supports ordered fallbacks and also fails over during provider initialization when the selected primary cannot be constructed.
