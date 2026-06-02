# 🤖 NexusAgent — Premium Offline-First AI Coding Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/nexus-agent/nexus-agent/workflows/Tests/badge.svg)](https://github.com/nexus-agent/nexus-agent/actions)
[![Lint](https://github.com/nexus-agent/nexus-agent/workflows/Lint/badge.svg)](https://github.com/nexus-agent/nexus-agent/actions)

NexusAgent is a state-of-the-art, fully offline-ready AI coding agent hosted entirely on your local machine. It combines the premium user experiences of *claude-code*, *opencode*, *letta*, *hermes*, and *codex* into a single, unified terminal (TUI) and high-fidelity dashboard (GUI).

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
irm https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.ps1 | iex
```

**Linux/macOS:**
```bash
curl -LsSf https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.sh | sh
```

**Manual:**
```bash
git clone https://github.com/nexus-agent/nexus-agent.git
cd nexus-agent
pip install -e ".[all]"
```

### First-Run Setup

```bash
# Launch the interactive setup wizard (recommended first time)
nexus wizard
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
