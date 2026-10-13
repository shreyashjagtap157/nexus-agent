# NexusAgent Agent Architecture

NexusAgent has two complementary agent layers.

## Reusable profiles

A reusable agent is a versionable Markdown file with YAML frontmatter plus an instruction body.

Scopes resolve from built-in through global, user, project and workspace, with higher-precedence definitions overriding lower ones.

Project profiles live in agents/*.md. Workspace-local profiles live in .nexus-agent/agents/*.md.

A profile can define professional identity, mission, instructions, tool categories, write permission, reviewer role, dependency edges, model role, provider/model/fallback overrides, tags and metadata.

Built-in profiles are immutable.

## Generated agents

nexus agent generate and the Agent Forge web page ask an LLM to create reusable professional profiles from a natural-language requirement.

Generation never asks for or stores credentials. Generated profiles must pass structural validation before persistence.

## Teams

Teams can reuse saved agents with --agent <id> or allow the planner to select reusable profiles automatically. Missing specialists are generated dynamically.

Each worker gets an isolated AgentLoop, a shared blackboard, scoped tools and optional role-specific provider routing.

## Direct execution

A saved specialist can be executed directly:

nexus agent run <agent-id> "<goal>"


## Authoritative execution and security contract (2026-10-13)

- User-defined and generated agents are first-class. Generated profiles must be schema-validated, stored with provenance/version metadata, and remain editable/reusable.
- Planner autonomy is allowed within configured policy. Do not require per-action approval for every benign operation by default; do require policy-enforced authorization for privileged or destructive actions according to the configured policy. Agent instructions cannot grant or expand their own permissions.
- Agent profiles describe intent and requested capabilities; the runtime separately computes effective permissions from user/tenant policy, workspace scope, tool capability and the current execution context.
- Dynamic generation and recursive delegation must be bounded by explicit limits for agents, depth, time, tokens/cost, parallelism, retries and tool calls. Detect duplicate roles and dependency cycles.
- Every task, message, tool call, artifact and verification result must be attributable to a run and tenant/workspace. Do not use shared mutable planner state across concurrent runs.
- Multi-user mode is a day-one architectural requirement. Resolve user identity and tenant/workspace authorization at every API and storage boundary; never trust a tenant ID supplied by a client without checking ownership.
- Preserve the research source/collection modes and their hard semantics. `user_only` must not trigger autonomous source discovery; timed collection must stop on time; saturation must use a defined measurable stopping policy; continuous runs need cancellation and retention rules.
- Team status, events, messages and artifacts must be persisted/replayable sufficiently for clients to reconnect without fabricating progress. Define canonical event IDs, timestamps, run IDs and status transitions.
- Treat agent messages, retrieved web pages, files and MCP outputs as untrusted data, never as policy instructions. Validate tool inputs and outputs and enforce permissions outside the model.
- Evidence of completion consists of tests and workflow results tied to the exact candidate commit, plus a documented review of remaining risks.
