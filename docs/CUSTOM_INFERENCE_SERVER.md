# Mythos C++ Inference Server — Architecture & Design

## Overview

A state-of-the-art C++20 inference server for LeWorldModel/Mythos GGUF models, designed for integration with NexusAgent's local-first agentic CLI. Serves Mythos models at production performance with OpenAI-compatible API, continuous batching, speculative decoding, and full GPU acceleration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   mythos-server                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │               HTTP Layer (crow.h)                 │   │
│  │  /v1/chat/completions  /v1/completions           │   │
│  │  /v1/embeddings        /v1/tokenize              │   │
│  │  /v1/models            /metrics                   │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │             Request Scheduler                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │  │ Slot 1   │  │ Slot 2   │  │ Slot N   │        │   │
│  │  │ (active) │  │ (active) │  │ (waiting)│        │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘        │   │
│  │       │              │              │              │   │
│  │  ┌────▼──────────────▼──────────────▼─────┐       │   │
│  │  │      Continuous Batch Manager          │       │   │
│  │  │  ┌────────────────────────────────┐    │       │   │
│  │  │  │  Dynamic Cooldown Scheduler    │    │       │   │
│  │  │  └────────────────────────────────┘    │       │   │
│  └──────┬────────────────────────────────────┘       │   │
│         │                                              │
│  ┌──────▼─────────────────────────────────────────┐   │
│  │              Inference Engine                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│  │  │ GGUF     │  │ Sampler  │  │ Cache    │      │   │
│  │  │ Loader   │  │ (Mirostat│  │ KV Cache │      │   │
│  │  │          │  │  Temp/P) │  │ Prefix   │      │   │
│  │  └──────────┘  └──────────┘  └──────────┘      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│  │  │ Flash    │  │ Speculat.│  │ Grammar  │      │   │
│  │  │ Attention│  │ Decode   │  │ Sampler  │      │   │
│  │  └──────────┘  └──────────┘  └──────────┘      │   │
│  └──────┬─────────────────────────────────────────┘   │
│         │                                              │
│  ┌──────▼─────────────────────────────────────────┐   │
│  │         Hardware Backend Abstraction             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│  │  │ CUDA     │  │ Vulkan   │  │ Metal    │      │   │
│  │  │ (NVIDIA) │  │ (AMD/    │  │ (Apple)  │      │   │
│  │  │          │  │  Intel)  │  │          │      │   │
│  │  └──────────┘  └──────────┘  └──────────┘      │   │
│  │  ┌──────────┐  ┌──────────┐                     │   │
│  │  │ SYCL     │  │ CPU      │                     │   │
│  │  │ (Intel)  │  │ (fallback│                     │   │
│  │  │          │  │  + GGML) │                     │   │
│  │  └──────────┘  └──────────┘                     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. GGUF Loader

```
class ModelLoader {
  - Memory-mapped file access (read-only, zero-copy)
  - Tensor loader: maps GGUF tensor blobs → GPU/CPU pointers
  - Architecture dispatcher: Mythos-specific (MLA, MoE, recurrent) or generic LLaMA
  - Quantization table: all 16 GGUF quantization types
  - Hot-reload: atomic swap of model pointer under read-lock
};
```

**Key design decisions:**
- Memory-map all weights at startup — no eager copies
- For GPU: async H2D transfer in background thread while warming KV cache
- Architecture detection from GGUF metadata; Mythos layers (recurrent block, JEPA head, MOE) get specialized kernels

### 2. Paged KV Cache

```
class PagedKVCache {
  - Block-based allocation (256 tokens/block)
  - Logical page table with physical block mapping
  - Copy-on-write for fork/speculative scenarios
  - Prefix caching: hash-based block dedup across requests
  - Eviction: LRU on physical blocks + guided eviction (keep system prompt blocks)
  - Sliding window support for long contexts (>32K)
};
```

### 3. Continuous Batching Scheduler

```
class ContinuousBatchScheduler {
  - Slot-based: N concurrent slots (configurable, default 64)
  - Dynamic cooldown: idle slot → release GPU memory after T seconds
  - Prefill priority: new requests prefill first (higher throughput)
  - Decode fairness: round-robin among active decodes
  - Max tokens per request: sliding cap per slot
  - Queue depth: unbounded with backpressure via HTTP 503
};
```

### 4. Speculative Decoding Engine

```
class SpeculativeDecodeEngine {
  - Draft model: smaller GGUF (e.g., Mythos-15M drafts for 350M target)
  - Lookahead: N tokens (default 5) per draft pass
  - Acceptance: rejection sampling with target model
  - Fallback: disable if draft model not loaded
  - Bonus tokens: up to 2 additional accepted tokens per round
  - Tree attention: parallel verification of draft tree
};
```

### 5. Sampler

```
class Sampler {
  - Temperature (with softmax scaling)
  - Top-P (nucleus) — adaptive threshold
  - Top-K
  - Mirostat v1/v2 — for local models to avoid repetition
  - Repetition penalty — frequency + presence
  - Grammar-based sampling via GBNF (compatible with llama.cpp grammars)
  - Logit bias — per-token additive biases
  - Dry sampling — context-aware repetition avoidance
};
```

### 6. HTTP API

```
REST API:
  POST /v1/chat/completions — OpenAI-compatible chat
  POST /v1/completions — Raw text completion
  POST /v1/embeddings — Embedding extraction (Mythos hidden states → pooling)
  POST /v1/tokenize — Token count / debug
  GET  /v1/models — List loaded models
  GET  /metrics — Prometheus metrics
  GET  /health — Health check

Streaming: Server-Sent Events (text/event-stream) for all /completions endpoints
Auth: Bearer token (optional, configurable), API-key per slot
```

### 7. Metrics & Observability

```
Prometheus metrics:
  mythos_requests_total{status,model}
  mythos_tokens_generated_total
  mythos_request_duration_seconds{quantile}
  mythos_time_to_first_token_ms
  mythos_tokens_per_second
  mythos_kv_cache_usage_blocks
  mythos_batch_slot_usage
  mythos_queue_depth
  mythos_gpu_memory_used_bytes
  mythos_gpu_utilization_percent

JSONL logging:
  request_log.jsonl — timestamp, model, tokens, latency, status
  error_log.jsonl — timestamp, error_class, trace, request_id
  perf_log.jsonl — per-step token timings, KV cache stats
```

## Build System

```
CMake Presets:
  cmake -B build --preset cpu       # GGML/CPU only
  cmake -B build --preset cuda      # NVIDIA GPU
  cmake -B build --preset vulkan    # AMD/Intel GPU
  cmake -B build --preset metal     # Apple Silicon
  cmake -B build --preset all       # Every backend

Dependencies (vendored):
  - crow.h (single-header HTTP) — HTTP server
  - nlohmann/json — JSON parsing
  - fmtlib — String formatting
  - spdlog — Structured logging
  - thread-pool — Work stealing thread pool
  - xxhash — KV cache block hashing

No external BLAS: uses GGML primitives directly or vendor math libraries
```

## Model Support Matrix

| Model | Size | Local | Colab | Server |
|-------|------|-------|-------|--------|
| Mythos-15M | 10M params | ✅ CPU | ✅ | ✅ Draft |
| Mythos-350M | 350M | ❌ | ✅ | ✅ Target |
| Mythos-3B | 3B | ❌ | ❌ (needs A100) | ✅ Target |
| LLaMA 3.x | 1B-70B | ❌ | ✅ | ✅ Via GGUF |
| Qwen 2.5 | 0.5B-72B | ❌ | ✅ | ✅ Via GGUF |
| DeepSeek | Varies | ❌ | ✅ | ✅ Via GGUF |

## Integration with NexusAgent

```
nexus-agent → mythos-server connection:
  1. NexusAgent launches mythos-server as subprocess on `nexus chat`
  2. Server loads requested GGUF model
  3. NexusAgent uses HTTP client (httpx) to call /v1/chat/completions
  4. Streaming SSE responses rendered in TUI/GUI
  5. Server shutdown on agent exit or idle timeout

Subprocess management:
  - Launch: `mythos-server --model mythos-350m-q4_k_m.gguf --port 8081`
  - Health polling: GET /health every 5s until 200
  - Graceful shutdown: POST /shutdown or SIGTERM
  - Crash recovery: auto-restart with exponential backoff (3 max)
  - Resource limits: process-level cgroup/Job object for RAM/CPU
```

## Implementation Phases

### Phase 1: Foundation (2-3 weeks)
- GGUF loader with memory-mapped reads
- CPU inference with GGML primitives
- OpenAI-compatible API (non-streaming)
- Single request, no batching

### Phase 2: Performance (2-3 weeks)
- CUDA backend for NVIDIA GPUs
- Continuous batching with slot management
- Streaming via SSE
- Paged KV cache with prefix caching

### Phase 3: Advanced (2-3 weeks)
- Speculative decoding with draft model
- Grammar-based sampling (GBNF)
- All GPU backends (Vulkan, Metal, SYCL)
- Prometheus metrics + JSONL logging

### Phase 4: Production (2 weeks)
- Hot-reload models without restart
- Authentication (Bearer token, API key)
- Rate limiting per slot
- Auto-detect optimal quantization
- Windows Job Object resource limits
- Integration tests with NexusAgent

## Performance Targets

| Metric | Target | Stretch |
|--------|--------|---------|
| TTFT (15M, CPU) | <50ms | <20ms |
| TTFT (350M, CUDA) | <100ms | <50ms |
| Tokens/s (350M, CUDA) | >100 t/s | >200 t/s |
| Tokens/s (3B, CUDA) | >30 t/s | >50 t/s |
| Batch slots | 64 | 128 |
| KV cache (350M, 32K) | 2GB VRAM | 1GB |
| Max queue depth | 256 | 512 |
| Uptime | 99.9% | 99.99% |

---

## Related Files

- NexusAgent LLM backend: `src/nexus_agent/llm/local_engine.py` (current Python-based llama-cpp-python integration)
- GGUF model support: via llama-cpp-python; mythos-server replaces this
- Config: `config/default.yaml` — add `server: { type: mythos, path: ..., port: ... }`
- Test framework: `tests/` — add integration tests for mythos-server subprocess management
