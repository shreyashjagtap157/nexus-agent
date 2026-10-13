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


## Qualification and policy contract (2026-10-13)

### Planning and execution bounds

Planning is allowed to select saved profiles and generate missing specialists, but generation and delegation must have explicit limits for agent count, depth, time, token/cost, parallelism, tool calls and retries. Detect duplicate roles and cycles. Use a deterministic terminal outcome when the plan is complete or the budget is exhausted; do not continue indefinitely because an agent asks to re-plan.

Every run owns its mutable planner state, task graph, cancellation token, budget counters and event stream. Shared data between workers must be explicit, versioned and concurrency-safe.

### Autonomy and permissions

The default product policy is autonomous execution within configured permissions. The runtime resolves effective permissions for each tool invocation using the authenticated actor, tenant/workspace, profile grants, tool risk and current policy. Prompts and generated agent profiles are untrusted inputs and cannot grant permission. High-impact actions may require approval according to configured policy; routine allowed work should not be blocked by unnecessary approval prompts.

### Multi-user execution

Task, team, worker, artifact, memory and event IDs are not authorization. Every API, background job and storage query must enforce ownership. Use tenant-aware quotas for concurrent runs, provider spending, tool execution and artifact size. Cancellation and resume requests must be checked against run ownership.

### Durable events and recovery

Record state transitions and tool outcomes with stable event IDs and timestamps. Clients must be able to reconnect and recover a coherent view of the run from persisted state/event replay. Cancellation must be propagated; failed workers must not leave dependencies permanently pending. Retry only transient/retryable failures within a bounded budget, and retain the final reason when a run cannot complete.

### Research stopping conditions

- `user_only`: never autonomously discover or fetch unapproved external sources.
- `timed`: enforce the configured wall-clock deadline even if workers are blocked.
- `until_saturation`: use explicit measurable marginal-yield/novelty criteria and a hard maximum budget.
- `continuous`: require cancellation, retention and resource-limit policies.
- Research depth must alter concrete collection/verification policies rather than only changing a prompt.
