# Security Policy

> **Last reviewed:** 2026-10-09

Workspace-sensitive GUI, team, memory, agent-profile, research-source, MCP, skill, audit and credential-metadata APIs are restricted to loopback clients and fail closed when client information is missing. Provider discovery endpoints are read-only. Autonomous research fetching validates each redirect target before following it and limits redirects to five hops.

## Supported Versions

| Version | Security support |
| --- | --- |
| 0.3.0-alpha.4 | Prerelease; qualification is in progress. Do not treat this as a production-supported release. |

## Reporting a Vulnerability

Please do not publish exploit details in a public issue. Use GitHub's private vulnerability reporting for this repository. Include the affected version/component, impact, and minimal reproduction steps.

## Security Model

### Command execution

- Commands are parsed into argument vectors and invoked with `shell=False`; the application does not execute user commands through `cmd.exe`.
- Windows command-interpreter launchers and `.bat`/`.cmd` files are refused by the sandbox. Common Windows `echo`, `dir`, and `type` built-ins are handled directly without invoking a shell.
- Commands are risk-classified and sandbox execution enforces timeouts, output limits and workspace boundaries. This is defense in depth, not an OS-level process sandbox; do not run untrusted agents with privileges you would not grant to the input being processed.
- User-controlled paths are resolved and checked against the selected workspace for file operations and team artifacts.

### Local web API

The GUI and team APIs are intended for local use. Workspace-sensitive endpoints check that the connecting client is loopback. A TLS reverse proxy does not make these endpoints suitable for remote use by itself: do not expose them remotely unless the authentication, trusted-proxy model and authorization policy are deliberately redesigned and tested.

### Credential storage

Provider credentials are kept separate from ordinary configuration. When the operating-system keyring is selected and available, the store uses it; the file backend uses a local credential file with restrictive permissions where supported. File storage is **not** encryption at rest, so use appropriate OS account and disk protections.

### Research evidence and SSRF

Research source capture fetches authoritative content itself instead of trusting worker-supplied content as a source snapshot. Private/local destinations are blocked for autonomous fetches, and each redirect hop is checked before the next request. Claim verification checks exact quotation presence in stored source text. Changing a claim's evidence invalidates prior successful verification records so current coverage cannot reuse stale verification.

## Dependency Security

CI audits the resolved third-party dependency set with `pip-audit` and runs CodeQL. The audit has one narrowly scoped temporary exception:

- **`PYSEC-2026-2447` / CVE-2025-69872 in `diskcache` at or below 5.6.3.** `llama-cpp-python` requires `diskcache` transitively. NexusAgent uses the `Llama` inference interface but does not instantiate `LlamaCache` or use DiskCache directly. The upstream advisory currently lists no patched version and describes exploitation when an attacker can write to a cache directory before the application reads from it. CI ignores only this advisory ID; all other discovered vulnerabilities remain fatal.

This exception is temporary and must be re-evaluated when upstream publishes a fix, the dependency graph changes, or code starts using `LlamaCache`/DiskCache. Do not store untrusted serialized entries in a cache directory writable by another principal. Remove the exception once a patched release or a verified dependency-removal path is available.

## CI and release requirements

- CI must run on pull requests and enforce the aggregate `CI / Required` status.
- Security checks must enforce `Security / Required`.
- Release qualification must be based on observed test, lint, type-check, native-build and security results; queued or skipped jobs are not passes.
- Repository administration must protect the canonical `main` branch, require pull-request review and the required status checks, disallow force-push/delete, and keep the default branch consistent with the documented workflow.

Do not commit credentials or private customer data. Report findings privately and retain enough evidence to reproduce and fix them.
