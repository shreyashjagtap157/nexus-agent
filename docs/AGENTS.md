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
