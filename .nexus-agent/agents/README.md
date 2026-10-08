# Project Agent Profiles

This directory contains project-shared NexusAgent agent definitions.

Each `*.md` file uses YAML frontmatter plus a Markdown instruction body. These profiles are intentionally version-controlled with the project.

Runtime state, credentials, caches, memory databases, sessions, team telemetry, research ledgers and trash live under `.nexus-agent/runtime` or the user data directory and are ignored by this directory's `.gitignore`.

Scope precedence is:

built-in < global < user < project < workspace

A higher-precedence definition with the same `id` overrides a lower-precedence profile.

Do not store API keys, passwords, OAuth tokens or other secrets in agent profile files.
