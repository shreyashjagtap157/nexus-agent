# Quick Start Guide

This guide gets you from zero to a working NexusAgent session in 5 minutes.

---

## Step 1: Install

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.ps1 | iex
```

### Linux/macOS (curl)
```bash
curl -LsSf https://raw.githubusercontent.com/nexus-agent/nexus-agent/main/install.sh | sh
```

### Manual
```bash
pip install -e ".[all]"
```

---

## Step 2: First-Run Setup

```bash
# Launch the interactive setup wizard (recommended first time)
nexus wizard

# The wizard will:
# - Detect your hardware (CPU, GPU, RAM)
# - Recommend an appropriate model size
# - Ask about permission mode (suggest / ask / auto)
# - Ask about memory mode (full / session-only)
# - Configure guardrails
# - Optionally add cloud API keys
```

---

## Step 3: Download a Model

Place GGUF files in `~/.nexus-agent/models/`. Example sources:

| Model | Quantization | Size | Best For |
|-------|-------------|------|----------|
| llama-3.2-3b | Q4_K_M | 2.0 GB | CPU-only, fast |
| qwen2.5-7b | Q4_K_M | 4.9 GB | Balanced |
| llama-3.1-8b | Q4_K_M | 4.9 GB | General coding |
| llama-3.1-70b | Q4_K_M | 40 GB | Best quality |
| phi-4-14b | Q4_K_M | 8.5 GB | Fast, good quality |

Download from: [HuggingFace GGUF models](https://huggingface.co/models?search=gguf)

---

## Step 4: Start Chatting

```bash
# Interactive TUI (recommended)
nexus chat

# Web GUI dashboard
nexus gui

# Single-prompt mode
nexus chat --prompt "Write a Python quicksort"
```

---

## What's Next?

- **[Local Models](local_models.md)** — Deep dive into GGUF setup, GPU offloading, context size tuning
- **[Cloud Providers](cloud_providers.md)** — OpenAI, Anthropic, Gemini, Groq, and more
- **[CLI Reference](cli_reference.md)** — All `nexus` subcommands and flags
- **[Configuration](configuration.md)** — YAML config, environment variables, `nexus config set`