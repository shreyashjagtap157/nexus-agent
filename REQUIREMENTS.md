# NexusAgent — Master Requirements & Specification Index

> **Version:** 0.1.0 (2026-05-31)
> **Status:** Planning — Pre-Execution
> **Read this first.** Then follow links to detailed documents.

---

## 1. PROJECT VISION

**NexusAgent** is an **offline-first, local-LLM-powered AI coding agent** that runs on any OS (Windows → Linux → iOS), any processor (CPU, GPU, NPU, TPU), and competes with — and exceeds — every existing coding agent including Claude Code, opencode, Codex, Cursor, and GitHub Copilot.

**The Core Differentiator:** NexusAgent loads GGUF/ONNX LLM models directly on the user's machine via `llama-cpp-python` and `onnxruntime-genai`. No cloud API required. **No existing agent does this.**

---

## 2. DESIGN PRINCIPLES

| # | Principle | Meaning |
|---|-----------|---------|
| 1 | **Offline-First, Cloud-Optional** | Local model hosting is the default. Cloud providers are add-ons. |
| 2 | **State-of-the-Art in Every Dimension** | CLI, GUI, speed, features, UX, extensibility — no compromises. |
| 3 | **Multi-Platform from Architecture** | Windows first, then Linux, then iOS. Same core, platform-specific UI. |
| 4 | **Multi-Processor** | CPU (via llama.cpp), GPU (CUDA/Vulkan/Metal/ROCm), NPU (ONNX/DirectML), TPU (cloud). |
| 5 | **Competitive Supremacy** | Match or exceed Claude Code, opencode, Codex, Cursor in every feature category. |
| 6 | **Extensible by Design** | Skills (Markdown) → MCP (JSON-RPC) → Python Plugins — layered extensibility. |
| 7 | **User Controls Everything** | Memory mode, permission model, model choice, update behavior — all configurable. |
| 8 | **Production Quality** | 0 security issues, comprehensive tests, full documentation, polished UX. |

---

## 3. DOCUMENT MAP

```
REQUIREMENTS.md  ← YOU ARE HERE (master index)
├── docs/ARCHITECTURE.md     — System architecture, data flow, module layering
├── docs/API.md              — REST API, WebSocket protocol, MCP interface
├── docs/ROADMAP.md          — Phased execution plan with timelines
├── docs/TEST_PLAN.md        — Testing strategy, coverage targets, CI/CD
├── docs/CONTEXT.md          — Current project state (updated from audit)
├── docs/FRESH_AUDIT.md      — File-by-file audit (already created)
├── docs/INSTALL.md          — Installation guide for all platforms
└── docs/CHANGELOG.md        — Version history
```

---

## 4. CORE FEATURES (Prioritized)

### Tier 0 — Must Have (Ship Blockers)
- [ ] Secure shell command execution (no injection risk)
- [ ] Local GGUF model loading and inference
- [ ] Basic agent loop (gather → act → verify)
- [ ] File read/write/edit tools
- [ ] Working CLI mode (`nexus chat`)
- [ ] Working Web GUI mode (`nexus gui`)
- [ ] First-run model setup wizard
- [ ] Permission system (allow/ask/deny)
- [ ] Session persistence across restarts
- [ ] Basic error handling (no silent crashes)

### Tier 1 — Core Excellence
- [ ] Dual CLI modes: lightweight streaming + rich TUI dashboard
- [ ] Streaming LLM responses in real-time
- [ ] Tool calling with all major LLM providers
- [ ] Diff visualization in CLI and GUI
- [ ] Memory system (working/long-term/episodic)
- [ ] Git integration (status, diff, commit, branch)
- [ ] Cloud provider support (9+ providers)
- [ ] Web search tool
- [ ] Config system (YAML + CLI flags + wizard)

### Tier 2 — Competitive Advantage
- [ ] Self-healing execution engine
- [ ] Reflection/critique loops
- [ ] Multi-agent orchestration (planner → executor → reviewer)
- [ ] RAG codebase search (FTS5 + symbol-aware)
- [ ] Skill system (Markdown SKILL.md files)
- [ ] MCP protocol support
- [ ] DevOps verification pipeline (linters, secrets, tests)
- [ ] Multi-agent debate code review
- [ ] Task graph DAG decomposition
- [ ] NLA telemetry and reasoning logging
- [ ] Smart git commits and PR generation

### Tier 3 — Future (Post-Launch)
- [ ] Python plugin system
- [ ] Native desktop apps (Tauri/Electron)
- [ ] iOS app
- [ ] Cloud sync across machines
- [ ] Collaborative multi-user sessions

---

## 5. KEY TECHNICAL DECISIONS (Approved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Core language | **Python 3.10+** | llama-cpp-python, ONNX runtime, FastAPI, AI/ML ecosystem |
| CLI framework | **Textual (optimized)** + lightweight mode | Both modes per user requirement |
| GUI backend | **FastAPI + WebSockets** | Async, native Python, streaming |
| GUI frontend | **Vanilla HTML/CSS/JS → PWA** | Start simple, upgrade to framework later |
| Model format | **GGUF (default) + ONNX** | User chooses; auto-detect hardware |
| Memory | **SQLite FTS5** | Zero dependencies, offline, good enough |
| Config | **YAML + CLI flags + wizard** | Three-layer approach |
| Updates | **Check on startup, notify, user decides download** | Non-intrusive, user-controlled |
| Extensibility | **Skills → MCP → Plugins** | Layered, implemented in order |
| Testing | **pytest, 80%+ coverage, CI/CD** | Comprehensive from the start |
| Versioning | **Semantic + date-based** | MAJOR.MINOR.PATCH + YYYY.MM.DD |

---

## 6. EXECUTION ROADMAP (Summary)

See `docs/ROADMAP.md` for full detail.

```
Phase A: Critical Fixes (Days 1-2)    → P0 security/stability issues
Phase B: Core Refactoring (Days 3-5)  → P1 architecture issues
Phase C: Completeness (Days 5-8)      → Missing components + tests
Phase D: Polish (Days 8-10)           → Docs, install, CI/CD
```

---

## 7. COMPETITIVE FEATURE MATRIX (Target)

| Feature | Claude Code | opencode | Codex | Cursor | **NexusAgent** |
|---------|:-----------:|:--------:|:-----:|:------:|:--------------:|
| Local model hosting | ❌ | ❌ | ❌ | ❌ | **✅** |
| Offline-first | ❌ | ❌ | ❌ | ❌ | **✅** |
| CLI streaming | ✅ | ✅ | ✅ | ❌ | **✅** |
| Rich TUI | ❌ | ✅ | ❌ | ❌ | **✅** |
| Web GUI | ❌ | ❌ | ❌ | ❌ | **✅** |
| All GPU backends | ❌ | ❌ | ❌ | ❌ | **✅** (CUDA/Vulkan/Metal/ROCm) |
| NPU support | ❌ | ❌ | ❌ | ❌ | **✅** (ONNX/DirectML) |
| Cloud providers | 1 | 75+ | 1 | 1 | **9+** |
| Self-healing | ✅ | ❌ | ❌ | ❌ | **✅** |
| Memory persistence | ❌ | ❌ | ❌ | ❌ | **✅** |
| Multi-agent debate | ❌ | ❌ | ❌ | ❌ | **✅** |
| DevOps pipeline | ❌ | ❌ | ❌ | ❌ | **✅** |
| MCP support | ✅ | ✅ | ✅ | ❌ | **✅** |
| Skills system | ✅ | ❌ | ❌ | ❌ | **✅** |
| RAG codebase search | ❌ | ❌ | ❌ | ✅ | **✅** |
| Smart git commits | ❌ | ❌ | ❌ | ❌ | **✅** |
| Python plugins | ❌ | ❌ | ❌ | ✅ | **✅** (future) |
| Cross-platform | ✅ | ✅ | ✅ | ✅ | **✅** |
| All processors | ❌ | ❌ | ❌ | ❌ | **✅** |

---

## 8. APPROVAL GATE

This document represents the complete specification for NexusAgent v1.0. 
Once approved, execution begins with Phase A (Critical Fixes).

**Next step:** Review `docs/ROADMAP.md` for the detailed execution plan, then approve to begin.
