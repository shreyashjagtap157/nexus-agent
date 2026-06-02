# Cloud Providers Guide

NexusAgent works fully offline with local models. It also supports cloud providers for hybrid or cloud-augmented workflows.

---

## Supported Providers

| Provider | Model Examples | Environment Variable |
|----------|--------------|---------------------|
| OpenAI | gpt-4o, gpt-4o-mini | `OPENAI_API_KEY` |
| Anthropic | claude-sonnet-4, claude-3-5-sonnet | `ANTHROPIC_API_KEY` |
| Google | gemini-2.0-flash, gemini-1.5-pro | `GEMINI_API_KEY` |
| Groq | llama-3.1-70b, mixtral-8x7b | `GROQ_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-coder | `DEEPSEEK_API_KEY` |
| OpenRouter | Any OpenAI-compatible model | `OPENROUTER_API_KEY` |
| AWS Bedrock | claude-sonnet-4, llama-3.1-70b | AWS credentials |
| Ollama | Any locally running Ollama model | No key needed |
| Custom | Any OpenAI-compatible endpoint | Per-deployment |

---

## Setup with the Wizard

The easiest way to configure a provider:

```bash
nexus wizard
# Step 6 walks you through adding cloud API keys
```

---

## Manual Setup

### OpenAI

```bash
nexus config set providers.openai.api_key sk-your-key-here
nexus config set providers.active openai
```

### Anthropic

```bash
nexus config set providers.anthropic.api_key sk-ant-your-key-here
nexus config set providers.active anthropic
```

### Google Gemini

```bash
nexus config set providers.google.api_key your-gemini-key
nexus config set providers.active google
```

### Groq

```bash
nexus config set providers.groq.api_key gsk-your-key-here
nexus config set providers.active groq
```

---

## Switching Between Providers

```bash
# Use cloud provider
nexus chat --provider openai

# Force offline (local GGUF only)
nexus chat --offline

# Use specific model
nexus chat --model gpt-4o --provider openai

# With GUI
nexus gui --provider anthropic --model claude-3-5-sonnet-latest
```

---

## Hybrid Mode

Use local models for speed and cloud for large tasks:

```yaml
# config/default.yaml
providers:
  active: "local"           # Default: local
  local:
    default_model: "llama-3.1-8b-Q4_K_M.gguf"

  # Cloud is available but not default
  openai:
    model: "gpt-4o"
```

---

## Ollama (Local Daemon)

If you prefer Ollama as your local runtime:

```bash
# Install Ollama
ollama pull llama3

# In NexusAgent, use:
nexus config set providers.active ollama
nexus config set providers.ollama.model llama3

# Or via CLI
nexus chat --provider ollama
```