# NexusAgent Multi-Agent Platform

NexusAgent is a local-first agent runtime and workbench. A task can run as one agent or as a dynamically assembled team of specialized peer workers.

## Operating modes

- auto: infer the appropriate operating mode from the task
- code: repository/software engineering
- research: source collection and evidence-oriented investigation
- review: independent/adversarial review
- analysis: systems/domain analysis
- plan: planning and architecture
- automation: workflow/automation engineering

## Team execution

The team architect converts the goal into typed professional profiles:

- profession and mission
- role-specific instructions
- tool categories
- write permission
- reviewer responsibility
- model role
- dependencies

Workers run concurrently up to the configured parallelism. Each worker is a real AgentLoop instance with its own context.

Workers share a persistent SQLite blackboard at:

<workspace>/.nexus/teams.db

The blackboard stores:

- team metadata/configuration
- worker profiles and lifecycle
- direct/broadcast messages
- worker events and tool activity
- completion/failure records
- final synthesis

Every worker receives two team tools:

- team_send_message
- team_read_messages

This creates a structured team communication channel without forcing uncontrolled conversational cross-talk.

## Permissions

Team execution defaults to safe behavior. Read/search/web/git inspection tools can run through the normal permission system; write/edit/shell/commit-like operations remain subject to the configured permission policy.

The CLI exposes --yes for deliberate non-interactive runs that should automatically approve tool calls.

## CLI

After pip install -e .:

nexus-team run "Inspect this repository, implement the requested feature, test it, and independently review the result." --mode code --max-agents 6 --parallelism 4

Inspect a persisted team:

nexus-team show <team-id>

## Web console

The existing NexusAgent web application now exposes:

/team.html

The console shows:

- task and team controls
- generated professions
- agent lifecycle/state
- live counters
- peer messages
- execution events
- final synthesis

It shares the same provider/workspace state as the primary NexusAgent dashboard.

## Native client

nexus-rs/ remains the native Rust client and TUI. It is the native surface for the same agent runtime. The team runtime is implemented in the shared Python core and is available through the web and team CLI; native team controls can use the same local service/IPC boundary without duplicating orchestration logic.

## Design principle

NexusAgent deliberately keeps orchestration, permissions, tools, providers and persistence in the shared core while treating web, CLI/TUI and native clients as presentation/control surfaces.

That means a team started by the web client is the same type of persisted team that can be inspected by the CLI, and the native client does not need a second implementation of planning, provider routing, tool execution or team messaging.
