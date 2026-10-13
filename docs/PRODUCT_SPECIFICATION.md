# NexusAgent Product Specification

> Status: Normative product requirements. This document describes intended behavior, not proof of current implementation.
> Last reviewed: 2026-10-13.

## 1. Product definition and principles

NexusAgent is a local-first, provider-agnostic, general-purpose multi-agent workbench. Research is a first-class workload, not the product boundary. The platform must support coding, repository analysis, research, planning, review, automation, document production and user-defined workflows. It must perform real work through configured models and authorized tools; simulated agents and mock tool results do not satisfy acceptance.

Principles: one semantic runtime; evidence over claims; user-configurable and generated agents; bounded autonomy; provider neutrality; authorization enforced by the runtime; durable scoped state; observable execution; recoverability; measurable milestone gates.

## 2. Clients and shared runtime

Target clients are a web application, CLI/TUI and native desktop client. They may differ in presentation but must share task, agent, provider, permission, persistence and workflow semantics. Do not duplicate orchestration or security policy in clients. Document intentional client limitations and test shared behavior through each supported surface.

## 3. Agents and teams

Users must be able to create, inspect, edit, validate, persist, scope and reuse agent profiles. Users can request generated agents; the planner may identify missing capabilities and propose specialists. Generated profiles must be validated, inspectable and checked against model capabilities and tool permissions. Prefer a suitable existing profile over unnecessary duplication.

A task may use one agent or a dynamic team. The orchestrator must interpret the goal, define deliverables and acceptance criteria, construct a dependency graph, assign work, run independent tasks concurrently, exchange structured messages and artifacts, verify outputs and finalize. Roles are task-dependent; examples include planner, researcher, source gatherer, analyst, verifier, overseer, qualifier, response writer, implementer, tester and documentation specialist.

The lifecycle must represent relevant planned, ready, running, waiting, blocked, failed, cancelled, completed and verification states. Unknown dependencies and cycles fail explicitly. Bound agent count, nested generation, retries, re-planning and resource consumption. Cancellation must stop new dispatch and propagate to active work where possible.

## 4. Tool runtime and security

Support authorized terminal/process execution; file and directory read/write/edit/move/delete/restore; Git/repository inspection and coding tools; web search/fetch and optional browser automation; document/structured-data parsing; MCP discovery/invocation; memory, evidence, artifact and workflow operations.

Each tool defines validated inputs, outputs/errors, permissions, execution context, timeout/cancellation, audit events and resource limits. Mutations must be identifiable and safely scoped. Destructive file operations should be recoverable where practical.

Agent instructions do not grant privileges. Enforce permissions at each tool invocation for every client and agent. Treat model output, web content, local documents, tool results and MCP responses as untrusted. Enforce filesystem boundaries, command execution policy, redirect/network validation, secret handling and MCP trust. Sensitive local APIs fail closed on missing or invalid caller context.

## 5. Providers and models

Separate provider metadata, endpoint, authentication, model identifiers, capabilities and routing. Support local inference, hosted providers and custom endpoints, including OpenAI-compatible APIs where appropriate. Provider failures, timeouts, rate limits and fallbacks must be observable and bounded. Model compatibility must be explicit for required features such as tool calling and structured output.

Requested NVIDIA NIM evaluation configuration: model nvidia/nemotron-3.5-lightning-30b-a3b at https://integrate.api.nvidia.com/v1/chat/completions. This is a configuration target, not a claim of live availability. Never commit or log credentials.

## 6. Research

Source modes:
- user_only: only user-supplied/authorized sources; do not silently expand to autonomous discovery.
- hybrid: combine user sources and permitted discovery.
- autonomous: discover sources according to configured policy.

Collection modes:
- single: one bounded pass.
- timed: stop at an explicit time budget.
- until_saturation: stop when a documented novelty/coverage criterion is met, subject to hard limits.
- continuous: ongoing collection with explicit lifecycle, persistence and cancellation.

Depth ranges from surface to exhaustive and must change operational budgets, not merely prompt wording. Local source directories must be explicitly authorized and preserve provenance. Browser automation is optional and must degrade cleanly when disabled or unavailable.

Evidence must distinguish source discovery, successful retrieval, extracted content, claims, quotations, verification, contradictions and synthesis. Agent assertion alone is not verification. Concurrent evidence writes must not silently overwrite each other.

## 7. Memory, sessions and persistence

Support global, user, workspace and project memory with documented precedence, ownership and isolation. Keep conversation history, active session/task state, durable memory, agent profiles, workflow definitions, evidence/source snapshots, artifacts, logs/events, provider configuration and credentials distinct.

Define create/read/update/delete semantics, provenance where useful, conflict handling, concurrent writes, retention, migrations, partial-write recovery and session resumption. Cross-user, cross-project or cross-workspace leakage is release-blocking. Store credentials separately from ordinary project configuration.

## 8. Activity, events and outputs

The activity UI must show real agent creation, assignments, dependencies, messages, artifact transfers, tool calls/results, errors, retries, cancellations, verification and finalization. Events need stable identifiers, timestamps, task/agent correlation and replay/persistence where required. Support chat output, file output or both. Record artifact identity/path, producing task/agent, format, validation status and access boundary.

## 9. Configuration

Validate configuration and report useful errors. Document precedence among packaged defaults, user configuration, project/workspace configuration and environment overrides. Security controls cannot be weakened by agent prompts. Derive actual supported variables/defaults from canonical config and runtime code; historical examples are not authoritative.

## 10. Engineering quality and acceptance

Test unit, integration, workflow and end-to-end behavior, including invalid inputs, denied permissions, provider timeout, cancellation, concurrent writes, interrupted sessions, client disconnects, malformed model output and missing optional dependencies.

CI must execute, not merely declare, checks. Required checks need stable names and successful runs for the exact candidate. Resolve security/dependency findings or use a documented narrow exception. Keep docs, manifests and version contracts synchronized.

A milestone is accepted only when requirements map to code/tests; relevant tests pass; supported clients exercise the behavior; security and persistence invariants have regression coverage; docs accurately describe behavior and limits; CI results correspond to the exact candidate commit; and remaining gaps/blockers are explicit.

This is the normative target. Current implementation status belongs in a dated, evidence-based audit.
