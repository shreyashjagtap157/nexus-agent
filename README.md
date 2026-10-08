# 🤖 NexusAgent — Local Multi-Agent Development & Research Workbench

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/shreyashjagtap157/nexus-agent/workflows/Tests/badge.svg)](https://github.com/shreyashjagtap157/nexus-agent/actions)
[![Lint](https://github.com/shreyashjagtap157/nexus-agent/workflows/Lint/badge.svg)](https://github.com/shreyashjagtap157/nexus-agent/actions)

NexusAgent is a local-first agent runtime and workbench for software engineering, research, analysis, automation and other tool-driven tasks. It supports the familiar single-agent workflow of modern coding agents while adding dynamically assembled multi-agent teams with concurrent specialist workers, a shared blackboard, explicit permissions and persistent telemetry.

Unlike traditional coding agents that force reliance on external cloud APIs, NexusAgent is built **local-first**, letting you load, hot-swap, and run local generative model runtimes (GGUF, ONNX) directly inside your machine's CPU, GPU, or Copilot+ PC NPU processors.

---

## ✨ Key Capabilities

* **🔌 100% Offline Local Model Hosting**: Directly loads GGUF models via high-performance `llama-cpp-python` and ONNX configurations optimized for Windows NPUs using `onnxruntime-genai`.
* **⚡ Premium TUI & Glassmorphic GUI**: Choose between a full-featured Textual terminal dashboard with an interactive workspace explorer, syntax-highlighted diff visualizer, and permission gating overlays, or a gorgeous glassmorphic web GUI.
* **🧠 Database-Backed Stateful Memory**: Employs MemGPT-inspired multi-tier memory (working LRU, long-term SQLite FTS5 recall, session episodies, and user preference profile learning).
* **💾 Dynamic Prompt Caching**: Dynamic caching of system configurations, large file fragments, and custom tools schemas to minimize processing latency.
* **👁️ Multimodal & Vision Support**: Robust abstract providers accommodating image input and vision backends to parse blueprints, flowcharts, and drawings.
* **🛡️ Safe Sandboxing & Git Isolation**: Safe command classification (suggest/ask/auto) coupled with strict Git Worktree isolation.
* **🧩 Modular Skill Registries**: Dynamic Markdown skill loaders (`SKILL.md` format) that parse YAML metadata block headers to spawn dedicated agent executors.
* **📡 Model Context Protocol (MCP)**: Extensible tool discovery via standard JSON-RPC 2.0 stdio MCP clients & servers.
* **🚀 First-Run Setup Wizard**: Interactive `nexus wizard` command guides hardware detection, model recommendation, and configuration.

---

## 👥 Multi-Agent Teams

A task can run as one agent or as a dynamically assembled team. The team architect generates professional roles from the task and operating mode, then runs eligible workers concurrently with role-specific tool access.

Supported modes: auto, code, research, review, analysis, plan and automation.

Team workers receive a dedicated AgentLoop context and shared team_send_message / team_read_messages tools. Team state, peer messages and events persist under .nexus/teams.db.

CLI:

    nexus-team run "Inspect the repository, implement the requested change, test it, and independently review the result." --mode code --max-agents 6 --parallelism 4

Named workflow example:

    nexus team run --workflow code-change "Implement this feature end-to-end and verify it."

Web team console:

    /team.html

## 🧭 Client Surfaces

| Surface | Entry point | Purpose |
|---|---|---|
| CLI/TUI | `nexus` | General agent interaction and commands |
| Team CLI | `nexus-team` | Dynamic multi-agent teams |
| Web GUI | `nexus gui` | Browser workspace and single-agent chat |
| Team Console | `/team.html` | Live team topology, messages and telemetry |
| Native client | `nexus-rs/` | Native Rust CLI/TUI over the agent backend |
## 🏗️ Technical Architecture

```
┌──────────────────────────────────────────────────┐
│                    USER                          │
│         (Terminal / Browser / API)               │
└─────────────┬───────────────┬────────────────────┘
              │               │
      ┌────────▼──────┐ ┌──────▼──────┐
      │   CLI (TUI)   │ │  GUI (Web)  │
      │   Textual     │ │  FastAPI    │
      └────────┬──────┘ └──────┬──────┘
               │               │
               └───────┬───────┘
                       │
               ┌───────▼───────┐
               │  Agent Core   │
               │  (AgentLoop)  │
               │  + Orchestrator│
               └───┬───┬───┬───┘
                   │   │   │
      ┌────────────┤   │   ├────────────┐
      │            │   │   │            │
┌────▼────┐ ┌────▼───▼┐ ┌▼─────┐ ┌────▼─────┐
│  Tools  │ │   LLM   │ │Memory│ │Sessions  │
│file,git,│ │Backend  │ │System│ │Checkpoint│
│shell,lsp│ │local+   │ │W/LT/ │ │Rollback  │
│edit,web │ │cloud    │ │Ep/UP │ │          │
└─────────┘ └────┬────┘ └──────┘ └──────────┘
                │
       ┌────────┼────────┐
       │        │        │
  ┌────▼──┐ ┌──▼───┐ ┌──▼────┐
  │Local  │ │Cloud │ │Ollama │
  │Engine │ │APIs  │ │Server │
  │(GGUF) │ │      │ │       │
  └───────┘ └──────┘ └───────┘
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **~10 GB** free disk space for models

### Installation

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/shreyashjagtap157/nexus-agent/master/install.ps1 | iex
```

**Linux/macOS:**
```bash
curl -LsSf https://raw.githubusercontent.com/shreyashjagtap157/nexus-agent/master/install.sh | sh
```

**Manual:**
```bash
git clone https://github.com/shreyashjagtap157/nexus-agent.git
cd nexus-agent
pip install -e ".[all]"
```

### First-Run Setup

```bash
# Launch the interactive setup wizard (recommended first time)
nexus wizard

# Discover providers and stored credential state
nexus provider list
nexus auth list
```

### Agent Profiles

```bash
nexus agent list
nexus agent init security-reviewer --scope workspace
nexus agent generate "Create a security auditor and a dependency analyst"
nexus agent run security-reviewer "Audit this repository"
```

### Running the Agent

```bash
# Interactive TUI dashboard (recommended first experience)
nexus chat

# Local web dashboard
nexus gui

# List available GGUF models
nexus model list

# Check hardware capabilities
nexus hardware

# Single-prompt mode (non-interactive)
nexus chat --prompt "Write a Python quicksort"
```

---

## ⚙️ Configuration

NexusAgent uses a layered config system (highest priority last):

```
default config  →  ~/.nexus-agent/config.yaml  →  ./.nexus-agent.yaml  →  NEXUS_* env vars
```

```bash
# View current config
nexus config show

# Set values persistently
nexus config set providers.active openai
nexus config set local_model.gpu_layers 32

# Or edit the YAML file directly
code ~/.nexus-agent/config.yaml
```

---

## 🌍 Supported Providers

| Provider | Best For | API Key |
|----------|----------|---------|
| **Local (GGUF)** | Privacy, offline, no cost | None |
| OpenAI | GPT-4o, GPT-4o-mini | `OPENAI_API_KEY` |
| Anthropic | Claude 3.5 Sonnet | `ANTHROPIC_API_KEY` |
| Google | Gemini 2.0 Flash | `GEMINI_API_KEY` |
| Groq | Fast inference | `GROQ_API_KEY` |
| DeepSeek | Cost efficiency | `DEEPSEEK_API_KEY` |
| OpenRouter | Access to 100+ models | `OPENROUTER_API_KEY` |
| AWS Bedrock | Enterprise | AWS credentials |
| Ollama | Local daemon | None |
| Custom | Any OpenAI-compatible API | Per-deployment |

---

## 📖 Documentation

| Guide | Description |
|-------|-------------|
| [docs/examples/getting_started.md](docs/examples/getting_started.md) | 5-minute quick start |
| [docs/examples/local_models.md](docs/examples/local_models.md) | GGUF setup, GPU offloading |
| [docs/examples/cloud_providers.md](docs/examples/cloud_providers.md) | Cloud API key setup |
| [docs/examples/cli_reference.md](docs/examples/cli_reference.md) | All `nexus` commands |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture & data flow |
| [docs/API.md](docs/API.md) | REST, WebSocket, and MCP API reference |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Development setup & PR guide |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model & best practices |
| [docs/AGENTS.md](docs/AGENTS.md) | Reusable and generated agents |
| [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md) | Named workflows and scheduling |
| [docs/STORAGE_AND_GOVERNANCE.md](docs/STORAGE_AND_GOVERNANCE.md) | Storage, credentials and file governance |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Provider catalog and routing |
| [docs/MULTI_AGENT_PLATFORM.md](docs/MULTI_AGENT_PLATFORM.md) | Dynamic peer teams, shared blackboard and client architecture |

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/nexus_agent --cov-report=html
```

---

## 📦 Optional Dependencies

```bash
pip install -e ".[cuda]"      # NVIDIA GPU acceleration
pip install -e ".[vulkan]"    # Cross-platform GPU (AMD, Intel)
pip install -e ".[metal]"     # Apple Silicon GPU
pip install -e ".[npu]"       # Windows NPU (Qualcomm, Intel)
pip install -e ".[providers]" # Cloud SDKs (OpenAI, Anthropic, etc.)
pip install -e ".[mcp]"       # Model Context Protocol support
pip install -e ".[all]"       # Everything
```

---

## 🛡️ Security

NexusAgent sandboxes all shell commands via `subprocess.run(shell=False)` and regex pattern detection. See [docs/SECURITY.md](docs/SECURITY.md) for the full security model.

---

## 📝 License

NexusAgent is open-source under the **MIT License**. See [LICENSE](LICENSE) or [Apache 2.0](NOTICE) for details.

---

## 🤝 Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for development setup, code style, and PR guidelines.
