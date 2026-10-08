# Security Policy

## Reporting a vulnerability

Do not disclose credentials, exploit details or unpublished vulnerabilities in public issues.

Use the repository's private GitHub security-advisory mechanism when available. If private advisory tooling is unavailable, open a minimal issue requesting a private contact channel without including sensitive details.

## Credential handling

NexusAgent stores provider credentials separately from project configuration. Never commit API keys, OAuth tokens, cookies, private certificates or production secrets.

Use the NexusAgent credential commands or environment variables.

## Tool permissions

Shell, file mutation, Git writes, MCP tools and other side-effecting tools remain permission-gated by default. Do not enable automatic approvals globally unless the execution environment is explicitly trusted.

## Suspected secret exposure

Rotate the credential immediately, then report the affected commit/path through the private security process.
