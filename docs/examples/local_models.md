# Local Models Guide

NexusAgent is built around local model hosting. This guide covers everything you need to know.

---

## How It Works

NexusAgent uses `llama-cpp-python` to load GGUF model files directly into RAM/VRAM. No cloud API required.

```
Your GGUF file → llama-cpp-python → Local LLM Engine → NexusAgent AgentLoop
```

---

## Supported Formats

| Format | Backend | Notes |
|--------|---------|-------|
| GGUF (Q4, Q5, Q6, Q8, F16) | llama-cpp-python | Primary format |
| ONNX (genai format) | onnxruntime-genai | NPU support |

---

## GPU Offloading

For NVIDIA GPUs, enable CUDA acceleration:

```bash
# Install with CUDA support
pip install -e ".[cuda]"

# Verify GPU is detected
nexus hardware

# Load a model with full GPU offloading (default)
nexus chat --model ~/models/llama-3.1-8b-Q4_K_M.gguf

# Or configure in config:
nexus config set local_model.gpu_layers -1
nexus config set local_model.gpu_backend cuda
```

### How many GPU layers to offload?

| VRAM | Recommendation |
|------|---------------|
| 4 GB | `gpu_layers=12` (partial) |
| 8 GB | `gpu_layers=32` (most) |
| 12+ GB | `gpu_layers=-1` (all) |

---

## GGUF File Naming Conventions

Model name patterns tell NexusAgent about size and quantization:

```
llama-3.1-8b-Q4_K_M.gguf
     ├── ────────┬───────
     │            └─── Quantization (Q4_K_M = recommended default)
     └── Parameter count (8 billion)
```

Quantizations ranked by quality (best → fastest):
```
F16 → Q8_0 → Q6_K → Q5_K_M → Q4_K_M → Q3_K_M → Q2_K
```

---

## Context Window Size

The context window determines how much code/text the model can "see" at once.

```bash
# Set to 8192 tokens (default is 4096)
nexus chat --model ~/models/llama-3.1-8b-Q4_K_M.gguf --context 8192

# Or in config:
nexus config set local_model.context_size 8192
```

For coding tasks, **8192-16384** tokens is recommended.

---

## Memory Guardrails

NexusAgent prevents loading models that would crash your system:

```bash
# Guardrail levels:
#   off     — Load any model (risk of OOM)
#   relaxed — Warn at 95% memory (allow)
#   balanced — Warn at 85% memory (recommended)
#   strict  — Block at 70% memory

nexus config set local_model.guardrails balanced
```

---

## Model Discovery

```bash
# List all models in your models directory
nexus model list

# Get detailed info about a specific model
nexus model info ~/models/llama-3.1-8b-Q4_K_M.gguf
```

---

## Auto-Detection

If you don't specify a model, NexusAgent will:

1. Check `~/.nexus-agent/models/` for GGUF files
2. Detect your hardware (RAM, VRAM)
3. Find the best-fitting model automatically

```bash
nexus chat --offline  # Force local-only mode
```