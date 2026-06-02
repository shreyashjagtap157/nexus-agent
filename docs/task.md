# NexusAgent — Build Tasks

## Phase 1: Foundation (Core + LLM + Config)
- [x] Project setup (pyproject.toml, directory structure, config files)
- [x] LLM base interface (`llm/base.py`)
- [x] Local LLM engine with llama-cpp-python (`llm/local_engine.py`)
- [x] Model manager for GGUF discovery (`llm/model_manager.py`)
- [x] Core agent loop (`core/agent.py`)
- [x] Context window management (`core/context.py`)
- [x] Sandbox execution (`core/sandbox.py`)
- [x] Entry point and CLI commands (`__main__.py`)
- [x] Config loader (`core/config.py`)
- [x] Add explicit GPU backend options to `llm/local_engine.py` (CUDA, Vulcan, ROCm, Metal)
- [x] Implement ONNX Runtime GenAI engine (`llm/onnx_engine.py`) for Windows NPUs
- [x] Add NPU hardware detection to `llm/model_manager.py`
- [x] Implement runtime/backend selector `RuntimeManager` (`llm/runtime_manager.py`)
- [x] Add multi-runtime options to `pyproject.toml` and `config/default.yaml`

## Phase 2: Tools & Memory
- [x] Tool base interface (`tools/base.py`)
- [x] File operations tool (`tools/file_ops.py`)
- [x] Shell command tool (`tools/shell.py`)
- [x] Code editing tool (`tools/code_edit.py`)
- [x] Git operations tool (`tools/git_ops.py`)
- [x] Web search tool (`tools/web_search.py`)
- [x] LSP client tool (`tools/lsp_client.py`)
- [x] Browser tool (`tools/browser.py`)
- [x] Memory manager (`memory/memory_manager.py`)
- [x] Working memory (`memory/working_memory.py`)
- [x] Long-term memory with SQLite FTS5 (`memory/long_term.py`)
- [x] Episodic memory (`memory/episodic.py`)
- [x] User profile learning (`memory/user_profile.py`)
- [x] Permission system (`permissions/manager.py`, `permissions/rules.py`)
- [x] Session management (`session/manager.py`, `session/storage.py`, `session/checkpoint.py`)

## Docs (Ongoing)
- [x] `docs/CONTEXT.md` — Full project context for LLM handoff
- [x] `docs/MEMORY.md` — Detailed implementation memory log

## Phase 3: CLI Interface
- [x] Textual TUI app (`cli/app.py`)
- [x] Chat view panel (embedded in `cli/app.py` with Rich Markdown rendering)
- [x] Status bar (embedded in `cli/app.py`)
- [x] File tree sidebar (`cli/file_tree.py` using Textual DirectoryTree)
- [x] Diff viewer (`cli/diff_view.py` unified code diff panel)
- [x] Command palette / slash commands (integrated into CLI commands list)
- [x] Agent activity panel (embedded in `cli/app.py` with custom logs)
- [x] TUI theme and styles (`cli/theme.py`, `cli/styles.tcss`)

## Phase 4: GUI Interface
- [x] FastAPI server (`gui/server.py`)
- [x] Chat API endpoints (embedded in `gui/server.py`)
- [x] Model management API (embedded in `gui/server.py`)
- [x] Session API (embedded in `gui/server.py`)
- [x] Settings API (embedded in `gui/server.py`)
- [x] WebSocket streaming (embedded in `gui/server.py`)
- [x] Frontend HTML (`gui/frontend/index.html`)
- [x] Frontend CSS (`gui/frontend/css/styles.css`)
- [x] Frontend JS — app, chat, models, settings, utils

## Phase 5: Advanced Features
- [x] Multi-agent orchestrator (`core/orchestrator.py`)
- [x] Planner agent (`core/planner.py`)
- [x] Executor agent (`core/executor.py`)
- [x] Skill loader (`skills/skill_loader.py`)
- [x] Skill registry (`skills/skill_registry.py`)
- [x] Built-in skills (code_review, refactor, debug, test_writer, documentation)
- [x] MCP client (`mcp/client.py`)
- [x] MCP server (`mcp/server.py`)
- [x] MCP transport (`mcp/transport.py`)
- [x] Cloud providers (OpenAI, Anthropic, Google, Ollama, OpenRouter, Groq, DeepSeek, Bedrock, Custom)

## Phase 6: Polish & Documentation
- [x] README.md
- [x] Configuration docs
- [x] Provider docs
- [x] Getting started guide
- [x] Build verification
- [x] Test suite

## Phase 7: Fine-Tuning & Premium CLI/GUI Options
- [x] Update `config/default.yaml` with advanced loading parameters & guardrails
- [x] Implement advanced loading settings in `LocalEngine`
- [x] Implement RAM/VRAM loading guardrails in `ModelManager`
- [x] Implement offline RAG search (`tools/rag_search.py`)
- [x] Implement atomic batch editor (`tools/batch_edit.py`)
- [x] Integrate reasoning effort and Hermes goals in `AgentLoop`
- [x] Add TUI commands & status monitors in `cli/app.py`
- [x] Add GUI endpoint settings & resource API in `gui/server.py`
- [x] Wrote new unit tests and verify build

## Phase 7.5: State-of-the-Art Upgrades (Advanced Control Loops)
- [x] Auto-discover repository rules (CLAUDE.md, AGENT.md) in `core/agent.py`
- [x] Add local JSONL telemetry tracing to `.nexus-agent/traces/` in `core/agent.py`
- [x] Implement Syntax Symbol-Aware RAG in `tools/rag_search.py`
- [x] Verify symbol retrieval weighting and trace files with automated tests
- [x] Update documentation logs (`docs/CONTEXT.md` and `docs/MEMORY.md`)

## Phase 8: Full-Spectrum Agent Capabilities
- [x] Implement dynamic/static Dual-Mode Web Crawler & Scraper (`tools/browser.py`)
- [x] Implement zero-dependency AST syntax diagnostics linter & definition lookup (`tools/lsp_client.py`)
- [x] Verify browser scraper fallback and AST compile linter checks with unit tests

## Phase 9: Full-Spectrum Agent Architecture (57 gaps across 18 categories)

### Phase 9A — Core Agent Intelligence
- [x] Component 1: Self-Healing Execution Engine (`core/self_heal.py`)
- [x] Component 2: Reflection & Critic Loops (`core/reflection.py`)
- [ ] Component 3: Hierarchical Task Graph (`core/task_graph.py`)
- [ ] Component 4: NLA Telemetry (`core/nla_telemetry.py`)
- [ ] Component 5: Multi-Agent Debate & Consensus (`core/debate.py`)

### Phase 9B — Verification & Quality
- [ ] Component 6: Autonomous DevOps Pipeline (`core/devops.py`)

### Phase 9C — Git & DevOps Intelligence
- [ ] Component 7: Smart Git tools (`tools/git_ops.py` enhancements)

### Phase 9D — Advanced Codebase Understanding
- [ ] Component 8: Code Intelligence tools (`tools/code_intel.py`)

### Phase 9E — Model & Runtime Intelligence
- [ ] Component 9: Smart Router in `llm/runtime_manager.py`

### Phase 9F — CLI & GUI Integration
- [ ] Wire into `core/agent.py` and `core/orchestrator.py`
- [ ] New CLI slash commands in `cli/app.py`
- [ ] New GUI API endpoints in `gui/server.py`
- [ ] Add Phase 9 unit tests to `tests/test_advanced.py`
- [ ] Update `docs/CONTEXT.md` and `docs/MEMORY.md`
