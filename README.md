# NexusAgent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/test.yml/badge.svg)](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/test.yml)
[![Lint](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/lint.yml/badge.svg)](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/lint.yml)
[![Security](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/security.yml/badge.svg)](https://github.com/shreyashjagtap157/nexus-agent/actions/workflows/security.yml)
[![Version](https://img.shields.io/badge/version-0.3.0--alpha.4-orange.svg)](VERSION)
[![Versioning Policy](https://img.shields.io/badge/versioning-SemVer-8A2BE2.svg)](docs/VERSIONING.md)

NexusAgent is a **local-first, multi-agent development and research workbench** designed to provide the capabilities users expect from modern agentic coding tools while allowing multiple professional agents to work together on one task.

It supports:

- single-agent coding and terminal workflows
- dynamically generated or user-authored multi-agent teams
- concurrent specialist workers with explicit professional roles
- shared team messaging, dependency-aware execution and persistent telemetry
- repository editing, shell execution, Git/CI, web research, browser automation, code intelligence, LSP, RAG, memory, formal checks and MCP
- local LLM execution plus hosted/custom OpenAI-compatible providers
- provider/model routing per agent
- secure provider credential storage
- web, CLI/TUI and native desktop clients
- evidence-first research with source/claim verification
- scoped persistent memory and explicit runtime storage boundaries

The active development version is **0.3.0-alpha.4**. This is an unreleased prerelease and is not a stable API commitment.

---

## Product model

NexusAgent has two complementary execution modes.

### Single-agent mode

Use NexusAgent like a conventional coding agent:

```bash
nexus chat
```

The agent can inspect the workspace, edit files, execute approved commands, use web/MCP tools, inspect Git state, use memory and continue working through an agentic loop.

### Multi-agent team mode

Give NexusAgent a goal and let it assemble a professional team:

```bash
nexus team run "Analyze the repository, implement the requested change, test it, and independently review the result." --mode code
```

The team architect can create roles such as:

- software architect
- implementation engineer
- test engineer
- security specialist
- repository analyst
- primary-source researcher
- evidence verifier
- contradiction/skeptic reviewer
- formal-methods specialist
- auditor
- synthesizer

Workers are real AgentLoop instances. They are not simulated placeholders. They communicate through a persistent team blackboard and can be given different tools, providers, models and permissions.

---

## Agent profiles

Agents can be created manually or generated from a natural-language request.

### List and inspect agents

```bash
nexus agent list
nexus agent show reviewer
nexus agent paths
```

### Create an editable profile

```bash
nexus agent init security-reviewer --scope workspace
```

Agent definitions are Markdown files with YAML frontmatter and are resolved using explicit scope precedence.

Supported scopes:

```
builtin
global
user
project
workspace
```

A workspace/project definition can intentionally override a broader profile without modifying the global or user definition.

### Ask NexusAgent to generate agents

```bash
nexus agent generate \
  "Create a compiler architect, implementation engineer, adversarial reviewer, and formal verification specialist for this repository" \
  --max-agents 6
```

Preview without saving:

```bash
nexus agent generate "Design a team for a security audit" --preview
```

Validate all loaded profiles:

```bash
nexus agent validate
```

Teams may pin saved agents while still generating additional specialists around them.

---

## Full tool surface

NexusAgent uses one shared tool architecture across its agent and team runtimes.

### Workspace and coding tools

- read files
- write files
- move/rename files
- reversible delete and restore
- structured-data parsing
- directory listing and file search
- code editing and batch editing
- symbol rename
- import/call graph analysis
- LSP queries
- repository RAG
- TODO persistence

### Execution and version-control tools

- terminal/shell execution
- Git operations
- smart commits
- pull-request generation
- CI analysis
- permission-gated mutation

### Internet and research tools

- web search
- direct web fetching
- browser automation
- configurable research sources
- source snapshots
- claim recording
- deterministic quotation verification
- contradiction and review coordination
- formal-analysis tools

### Memory and collaboration

- working/session memory
- persistent long-term memory
- user/project/workspace scoped memory
- agent/team/session scoped memory
- direct agent-to-agent messages
- broadcasts
- dependency-aware handoffs
- persistent team event history

### MCP

NexusAgent can load configured MCP servers and expose their tools to eligible agents. MCP remains a first-class capability rather than a separate research-only integration.

---

## Research mode

Research is a first-class workload, not a separate product.

The research engine supports explicit source strategies:

```
user_only
hybrid
autonomous
```

Users can provide seed sources or let the team discover sources automatically.

Research depth is configurable from a literal surface-level pass through increasingly exhaustive levels:

```
glance
surface
shallow
basic
preliminary
exploratory
focused
detailed
deep
very_deep
comprehensive
exhaustive
atomic
molecular
cellular
planetary
stellar
galactic
cosmic
universal
maximal
```

The depth setting controls operational budgets such as source collection, verification, contradiction analysis, formal analysis and independent review. A higher name does not imply that an LLM can literally inspect an atom or the universe; it defines a progressively larger research/search/verification budget.

### Evidence-first behavior

Research teams can persist:

1. source metadata and snapshots
2. exact source text
3. factual claims
4. supporting quotations
5. deterministic quotation verification results
6. contradictions and counterevidence
7. final quality-gate information

The report layer is designed so the synthesis phase can distinguish verified evidence from unresolved or unverified material.

---

## Output modes

Team runs support:

```
chat
file
both
```

Supported artifact formats:

```
markdown
text
json
```

Example:

```bash
nexus team run \
  "Produce an evidence-backed architecture report" \
  --mode research \
  --output both \
  --format markdown
```

---

## Long-running teams

Teams support lifecycle controls:

```bash
nexus-team control <team-id> pause
nexus-team control <team-id> resume
nexus-team control <team-id> stop
```

Control requests are persisted so another local client can observe or control a running team.

Team history is persistent and includes:

- team configuration
- worker roles
- worker state
- peer messages
- execution events
- synthesized output
- artifact paths
- quality/audit information

---

## Client surfaces

| Surface | Entry point | Role |
|---|---|---|
| Python CLI/TUI | `nexus` | Full interactive agent experience |
| Team CLI | `nexus-team` | Dedicated multi-agent team operations |
| Web app | `nexus gui` | Browser-based workspace and agent experience |
| Team Console | `/team.html` | Live team topology, activity and telemetry |
| Agent Forge | `/agents.html` | Create/edit/generate reusable agent profiles |
| Native Rust client | `nexus-rs/` | Native CLI/TUI over the shared backend |
| Native desktop | `nexus-desktop/` | Native egui control center |

The native clients are presentation/control surfaces over the shared runtime; orchestration logic is not duplicated into separate implementations.

---

## Provider architecture

NexusAgent is provider-agnostic.

It can use:

- local GGUF/ONNX inference
- OpenAI
- Anthropic
- Google
- xAI
- Mistral
- Groq
- Together AI
- Fireworks
- DeepInfra
- Cerebras
- SambaNova
- Perplexity
- Moonshot/Kimi
- OpenRouter
- NVIDIA NIM
- Hugging Face inference
- custom OpenAI-compatible endpoints

Model availability is intentionally not hardcoded into NexusAgent because hosted model catalogs change independently from the client release.

### Credentials

Credentials are separated from ordinary model/provider configuration.

```bash
nexus auth login --provider nvidia_nim
nexus auth list
nexus auth logout nvidia_nim
```

With the optional security dependencies installed, the credential store can use the operating-system keychain. Otherwise it uses a permission-restricted local credential file.

Do not commit provider keys to project configuration or source control.

### Per-agent routing

A team role may select its own:

```
provider
model
fallbacks
```

For example, a research verifier can use NVIDIA NIM with Nemotron while a low-cost search worker uses another provider.

---

## Configuration

NexusAgent uses layered configuration. Project/workspace configuration is separate from user credentials.

Typical configuration layers are:

```
packaged defaults
    ↓
user configuration
    ↓
project/workspace configuration
    ↓
environment overrides
```

The repository's canonical default configuration is:

```
config/default.yaml
```

The packaged runtime copy is:

```
src/nexus_agent/_default_config.yaml
```

Use:

```bash
nexus config show
```

and project/user configuration files instead of storing secrets in source-controlled configuration.

---

## Storage model

NexusAgent deliberately separates code/workspace state, persistent user state, credentials and runtime artifacts.

The main boundaries are:

```
Global
User
Project
Workspace
Agent
Team
Session
```

Workspace runtime state is kept below:

```
.nexus-agent/
```

The runtime layout includes dedicated areas for:

- agent definitions
- workspace/project memory
- teams
- research evidence
- artifacts
- RAG indexes
- todos
- reversible file trash

Provider credentials are stored outside the workspace runtime.

This separation allows projects to be shared without accidentally shipping personal memory, credentials or session history.

---

## Local installation

### Requirements

- Python 3.10+
- Git
- Rust toolchain for native clients
- optional local model runtime/hardware appropriate to your chosen backend

### Editable installation

```bash
git clone https://github.com/shreyashjagtap157/nexus-agent.git
cd nexus-agent

python -m pip install -e ".[all]"
```

### Start with the CLI

```bash
nexus chat
```

### Start the web app

```bash
nexus gui
```

### Native clients

```bash
cargo run --manifest-path nexus-rs/Cargo.toml
cargo run --manifest-path nexus-desktop/Cargo.toml
```

---

## Development and validation

Run the complete Python test suite:

```bash
python -m pytest tests/ -q
```

Run lint and formatting checks:

```bash
python -m ruff check src/
python -m ruff format --check src/
python -m mypy src/nexus_agent/
```

Validate the repository-wide version contract:

```bash
python scripts/check_version.py
```

The CI matrix covers multiple Python versions and operating systems, plus native client checks. Security analysis and dependency auditing run in GitHub Actions as part of the repository quality gates.

### Enterprise engineering governance

main is the canonical integration branch. Changes are expected to arrive through pull requests and pass the repository CI/security gates before merge.

The GitHub validation surface includes:

- complete Python regression testing across supported Python versions and Ubuntu, Windows and macOS
- Ruff formatting/linting and strict MyPy checks
- Rust formatting and compilation for both native clients across supported operating systems
- version-contract validation
- repeatable test/audit evidence artifacts
- CodeQL and dependency security checks
- automated dependency update pull requests through Dependabot

The expected GitHub-side protection policy for main is documented in [.github/BRANCH_PROTECTION.md](.github/BRANCH_PROTECTION.md). The policy requires pull-request review, Code Owner review, required status checks, conversation resolution, no force-pushes, and administrator enforcement.

All release tags are validated against main history before release publication. Release artifacts are built and provenance-attested in GitHub Actions.


---

## Versioning and release model

NexusAgent follows SemVer 2.0.0 syntax.

The repository-root `VERSION` file is canonical. Python, Rust, configuration and lockfile manifests must remain synchronized with it.

Current snapshot:

```
0.3.0-alpha.4
```

Development sequence:

```
0.y.z-alpha.N
    ↓
0.y.z-beta.N
    ↓
0.y.z-rc.N
    ↓
0.y.z
```

`1.0.0` is reserved for the point where the documented CLI, HTTP API, MCP/tool contracts, provider configuration, persistence formats, team protocol and native client/backend protocol have an explicit stability commitment.

Published tags are immutable and use:

```
v<version>
```

For the complete policy, see [docs/VERSIONING.md](docs/VERSIONING.md).

---

## Repository layout

```
src/nexus_agent/       Python agent/runtime
nexus-rs/              Rust CLI/TUI client
nexus-desktop/         Native egui desktop client
config/                Default configuration
docs/                  Architecture, operations and product documentation
tests/                 Python regression/integration tests
scripts/               Release/versioning utilities
```

---

## Documentation

| Document | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Runtime architecture and data flow |
| [docs/API.md](docs/API.md) | HTTP/MCP/API surfaces |
| [docs/AGENTS.md](docs/AGENTS.md) | Reusable and generated agents |
| [docs/MULTI_AGENT_PLATFORM.md](docs/MULTI_AGENT_PLATFORM.md) | Team architecture and coordination |
| [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md) | Workflows and scheduling |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Provider routing and model configuration |
| [docs/STORAGE_AND_GOVERNANCE.md](docs/STORAGE_AND_GOVERNANCE.md) | Storage, credentials and workspace governance |
| [docs/VERSIONING.md](docs/VERSIONING.md) | Release/version contract |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Security

NexusAgent uses permission-gated tools and workspace boundary checks for filesystem and shell operations. Destructive file operations use a reversible trash path by default.

Security-sensitive capabilities should be explicitly reviewed before enabling automatic execution in a production environment.

---

## License

NexusAgent is released under the MIT License. See [LICENSE](LICENSE).
