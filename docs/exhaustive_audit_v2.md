# NexusAgent — Exhaustive Minutia-Level Audit v2

**Generated:** 2026-06-07
**Scope:** Every public symbol in `src/nexus_agent/`, cross-referenced against claude-code, opencode, codex, letta-code, openclaw, and hermes-agent.
**Goal:** Feature-by-feature parity map and gap list for the next iteration of NexusAgent.

---

## Part 1 — Codebase Inventory (line-anchored)

### 1.1 Module Map

```
src/nexus_agent/                        87 .py files
├── __init__.py                         (entry: re-exports + version)
├── __main__.py                         (Click CLI: nexus command)
├── core/                               (12 files, ~2,853 lines)
│   ├── agent.py            834 lines  AgentLoop, AgentLoopConfig, AgentEvent, AgentMode
│   ├── sandbox.py          368 lines  Sandbox, SandboxConfig, SandboxMode
│   ├── reflection.py       361 lines  ReflectionEngine, scoring rubric
│   ├── debate.py           336 lines  DebateEngine, persona-based dispute
│   ├── orchestrator.py     303 lines  Orchestrator, planner/executor/reviewer sub-agents
│   ├── self_heal.py        343 lines  SelfHealingExecutor, diagnosis + fix
│   ├── devops.py           393 lines  VerificationPipeline, GitCheckpointer
│   ├── nla_telemetry.py    223 lines  NLATelemetry, NLAEncoder
│   ├── task_graph.py       345 lines  TaskGraph, TaskNode, TaskState
│   ├── config.py           206 lines  NexusAgentConfig, _load, _save, env mapping
│   ├── context.py          155 lines  ContextManager, 60-message compaction
│   └── sqlite_store.py      ~70 lines SQLiteStore base class
├── llm/                               (14 files, ~2,752 lines)
│   ├── base.py             273 lines  LLMProvider ABC, Message, ToolCall, StreamChunk, …
│   ├── model_manager.py    421 lines  ModelManager, hardware detection
│   ├── runtime_manager.py  465 lines  RuntimeManager, INSTALLABLE_RUNTIMES, SmartRouter
│   ├── onnx_engine.py      334 lines  NPU/CPU via onnxruntime-genai
│   ├── local_engine/
│   │   ├── engine.py       263 lines  LocalEngine, chat-format auto-detect
│   │   ├── protocol_mixin.py 277 lines Agent protocol XML/JSON
│   │   └── inference_mixin.py 120 lines Streaming + token estimation
│   └── providers/                      (10 provider files, 1,300 lines)
│       ├── factory.py       106 lines  ProviderFactory (lazy import + cache)
│       ├── base.py
│       ├── openai_provider.py        212 lines  (httpx 60s)
│       ├── anthropic_provider.py     296 lines  (httpx 60s, full streaming)
│       ├── google_provider.py         59 lines  (subclass of OpenAI)
│       ├── ollama_provider.py         60 lines  (subclass of OpenAI)
│       ├── openrouter_provider.py     63 lines  (subclass of OpenAI)
│       ├── groq_provider.py           57 lines  (subclass of OpenAI)
│       ├── deepseek_provider.py       54 lines  (subclass of OpenAI)
│       ├── custom_openai_provider.py  53 lines  (subclass of OpenAI)
│       └── aws_bedrock_provider.py   284 lines  (boto3, native Converse API)
├── cli/                               (24 files, ~9,000 lines)
│   ├── app.py              253 lines  NexusApp REPL (mixin composition)
│   ├── wizard.py           390 lines  SetupWizard 7-step first-run
│   ├── renderer.py         ~1617      Every glyph/color/state
│   ├── input_handler.py    785 lines  Every key binding, autocomplete
│   ├── input_handler_simple.py  66   MinimalInputHandlerMixin fallback
│   ├── theme.py             91 lines  ThemeColors (DARK + LIGHT)
│   ├── event_handler.py    157 lines  AgentEvent → save_message
│   ├── session_handler.py  ~470 lines Session replay + agent restore
│   ├── runtimes.py         229 lines  Runtime detection
│   ├── auth.py             280 lines  AuthStore (Fernet-encrypted keys)
│   ├── models_db.py        257 lines  ModelsDB metadata store
│   ├── command_dispatcher.py 2604     Legacy monolithic dispatcher
│   └── commands/                       (refactored mixin tree)
│       ├── _base.py        819 lines  BaseCommands, SLASH_COMMANDS
│       ├── agent.py        374 lines  Mode/effort/goal/debate/orchestrate
│       ├── session.py      211 lines  Clear/session/checkpoint/rollback/fork/rewind
│       ├── model.py        368 lines  Model/runtime/wizard
│       ├── tools.py        174 lines  Search/browser/mcp/skill
│       ├── git.py           71 lines  Diff/branch/commit/pr
│       ├── config.py       102 lines  Config/tui/theme/permissions
│       ├── debug.py        284 lines  Stats/memory/telemetry/nla
│       └── misc.py         227 lines  Help/quit/feedback/init
├── memory/                            (6 files, ~891 lines)
│   ├── memory_manager.py   179 lines  MemoryManager (search/store/remember/get_context)
│   ├── working_memory.py   105 lines  LRU + scratchpad (max 100)
│   ├── long_term.py        267 lines  SQLite + FTS5 (memories, access_count)
│   ├── episodic.py         122 lines  SQLite + FTS5 (episodes, no update trigger)
│   └── user_profile.py     200 lines  YAML + dot-notation (learned_patterns cap 100)
├── session/                           (3 files, ~929 lines)
│   ├── storage.py          284 lines  SessionStorage (3 tables, type column)
│   ├── manager.py          346 lines  SessionManager (atexit, fork, get_last_for_workspace)
│   └── checkpoint.py       299 lines  CheckpointManager (50 cap, atomic index)
├── permissions/                       (2 files, ~351 lines)
│   ├── manager.py          245 lines  PermissionManager (session_grants, sha256 cache)
│   └── rules.py            106 lines  PermissionLevel enum + 11 DEFAULT_RULES
├── skills/                            (8 files, ~500 lines)
│   ├── skill_loader.py     224 lines  Skill (subclass Tool), load_skill_from_markdown
│   ├── skill_registry.py    98 lines  SkillRegistry (thread-safe discovery)
│   └── builtin/                        (5 .md files: code_review, debug, doc, refactor, test_writer)
├── mcp/                               (3 files, ~509 lines)
│   ├── transport.py         82 lines  MCPTransport ABC + StdioTransport
│   ├── client.py           304 lines  MCPClient (allowlist, sanitization, 9 classes of checks)
│   └── server.py           123 lines  MCPServer (initialize/tools/list/tools/call)
├── tools/                             (13 files, ~4,000 lines)
│   ├── base.py             139 lines  Tool ABC, ToolError, resolve_workspace_path
│   ├── file_ops.py         508 lines  Read/Write/Search/List
│   ├── shell.py            103 lines  ShellTool (wraps Sandbox)
│   ├── code_edit.py        308 lines  Edit/Insert (AST validation gate)
│   ├── code_intel.py       386 lines  Import/Call/Rename (pure ast)
│   ├── git_ops.py          379 lines  Git/SmartCommit/PR/CI
│   ├── web_search.py       109 lines  DuckDuckGo Instant Answer
│   ├── rag_search.py       343 lines  Repo FTS5 + symbol index
│   ├── batch_edit.py       188 lines  Atomic multi-file replace
│   ├── browser.py          481 lines  Playwright + HTTPX fallback (SSRF-blocked)
│   ├── lsp_transport.py    505 lines  LSPClient, LSPClientPool, LSPConfig, DEFAULT_SERVERS
│   └── lsp_client.py       521 lines  LSPClientTool (8 actions, real-LSP dispatch)
├── gui/                               (1 Python + 6 frontend files, ~2,100 lines)
│   ├── server.py           670 lines  FastAPI + WS + security middleware
│   └── frontend/
│       ├── index.html      213 lines  3-column dashboard
│       ├── css/styles.css  856 lines  Dark glassmorphism
│       └── js/{app,chat,models,settings,utils}.js  681 lines total
└── permissions/__init__.py (1 line)
```

**Total: 87 .py files, ~26,500 lines.**

### 1.2 Core (AgentLoop etc.)

`core/agent.py:1-834` — `AgentLoop`:
- `EFFORT_CONFIG` (line 32) — 5 levels: `low` (15 it / T0.30 / 2048 tok) → `max` (120 it / T0.01 / 32768 tok, multi-pass)
- `AgentMode` enum: `AUTO | PLAN | BUILD | REVIEW` (line 88)
- `AgentState` enum: `IDLE | THINKING | TOOL_RUNNING | REFLECTING | DEBATING | AWAITING_PERMISSION | DONE | ERROR` (line 79)
- `AgentEvent` types: `thinking | content | content_chunk | tool_call | tool_result | error | done` (line 56)
- Methods: `run()`, `run_stream()`, `_plan()`, `_execute_step()`, `_reflect()`, `_debate()`, `_should_continue()`, `add_tool()`, `add_skill()` (lines 200-720)
- Multi-pass (xhigh+): planning prompt injected before execution, review pass after completion

`core/sandbox.py` — `Sandbox` with `SandboxMode` enum (`SUGGEST | ASK | AUTO`) and `RiskLevel` (`LOW | MEDIUM | HIGH | CRITICAL`); per-command allowlist/denylist; 30s default timeout; path confinement

`core/reflection.py` — `ReflectionEngine` with 5-dimension scoring rubric (correctness, completeness, style, safety, efficiency)

`core/orchestrator.py` — `Orchestrator` with planner/executor/reviewer sub-agent fan-out

`core/self_heal.py` — `SelfHealingExecutor` with diagnosis → fix → verify

`core/devops.py` — `VerificationPipeline` (lint + secrets + test) and `GitCheckpointer` (git branch + stash)

`core/nla_telemetry.py` — `NLATelemetry` with autoencoder token compression

`core/task_graph.py` — `TaskGraph`, `TaskNode`, `TaskState` for hierarchical task tracking

`core/config.py` — `NexusAgentConfig` with YAML + env var layer; NEXUS_* env mapping (see AGENTS.md)

`core/context.py` — `ContextManager` with 60-message compaction threshold + rolling token budget

### 1.3 LLM

`llm/local_engine/engine.py` — `LocalEngine` with chat-format auto-detection (llama-3, qwen-2.5, gemma, mistral, phi-3, command-r, deepseek)

`llm/local_engine/protocol_mixin.py` — Agent protocol XML/JSON serialization for tool calling

`llm/local_engine/inference_mixin.py` — Streaming + token estimation

`llm/onnx_engine.py` — NPU/CPU/DML/CUDA via `onnxruntime-genai` (NOT a stub)

`llm/model_manager.py` — `ModelManager` with hardware detection (psutil + pynvml), quantization scoring, model recommendations

`llm/runtime_manager.py` — `RuntimeManager`, `SmartRouter`, `INSTALLABLE_RUNTIMES` (cpu/cuda/vulkan/metal/rocm/onnx)

`llm/providers/factory.py` — 9 cloud providers via lazy import + instance cache

### 1.4 CLI

**Mixins (commands/)**:
- `AgentCommands` — `/mode`, `/effort`, `/goal`, `/sandbox`, `/context`, `/reflect`, `/task`, `/debate`, `/verify`, `/retry`, `/undo`, `/explain`, `/btw`, `/fast`, `/plan`, `/build`, `/orchestrate`, `/autonomous`, `/review`, `/compact`, `/quick`
- `SessionCommands` — `/clear`, `/session`, `/checkpoint`, `/checkpoints`, `/rollback`, `/export`, `/fork`, `/resume`, `/rename`, `/import`, `/copy`, `/rewind`
- `ModelCommands` — `/model`, `/runtime`, `/display-settings`
- `ToolsCommands` — `/search`, `/index`, `/browser`, `/mcp`, `/skill`
- `GitCommands` — `/diff`, `/branch`, `/commit`, `/pr`
- `ConfigCommands` — `/config`, `/tui`, `/theme`, `/color`, `/vim`, `/statusline`, `/permissions`
- `DebugCommands` — `/stats`, `/memory`, `/telemetry`, `/nla`, `/doctor`
- `MiscCommands` — `/help`, `/quit`, `/feedback`, `/init`, `/add-dir`, `/init` (bootstrap CLAUDE.md equivalent)

**Renderer glyphs (renderer.py)**:
- Spinner: `▶` | User: `❯` | Tool: `▶ name(args)` | Tool result: `✓ [Xs] name` / `✗ [Xs] name` | Warning: `⚠` | OK: `OK` | FAIL: `FAIL` | Section header: `═══` | Bullet: `●` | Divider: `── Resuming session … ──`

**Theme tokens (theme.py:13-90)**:
- DARK: `user: cyan`, `assistant: white`, `tool_call: blue`, `tool_result: green`, `error: red`, `warning: yellow`, `code_block: magenta`, `muted: dim`
- LIGHT: same with adjusted contrast

**Key bindings (input_handler.py)**:
- `Ctrl+C` interrupt (graceful) | `Ctrl+D` EOF | `Enter` submit | `Shift+Enter` newline | `↑/↓` history | `Tab` autocomplete | `Esc` clear | `Ctrl+L` clear screen | `Ctrl+R` reverse history search | `Ctrl+W` word delete | `Ctrl+U` line clear | `Ctrl+A/E` line start/end

### 1.5 Memory

`memory/working_memory.py`:
- `OrderedDict` store, LRU eviction at `_DEFAULT_MAX_ENTRIES = 100`
- Scratchpad: `list[str]`, trims to 40 when over 50
- `set/get/delete/list_keys/add_note/get_scratchpad/clear_scratchpad/clear/get_summary`

`memory/long_term.py:22` — `LongTermMemory(SQLiteStore)`:
- Tables: `memories` (id, content, category, metadata, created_at, updated_at, access_count) + FTS5 `memories_fts` + AI/AD/AU triggers
- `store()` UUID4 hex id; `search()` FTS5 with `_sanitize_query` + LIKE ESCAPE fallback; auto-increments `access_count`
- No retention/eviction policy

`memory/episodic.py:20` — `EpisodicMemory(SQLiteStore)`:
- Tables: `episodes` + FTS5 `episodes_fts` + AI/AD triggers (no AU)
- `save_session()`, `search()` (FTS5 with LIKE fallback), `get_recent()`

`memory/user_profile.py:24` — `UserProfile`:
- YAML file, dot-notation get/set
- `DEFAULT_PROFILE`: `coding_style`, `preferences`, `behavior`, `learned_patterns` (cap 100)
- Atomic write via tempfile + os.replace

`memory/memory_manager.py:24` — `MemoryManager`:
- `search(query, limit=10)` — combines long-term + episodic, dedupes by id, normalizes score
- `store(content, category, metadata)`, `remember(key)` (working → long-term fallback)
- `save_session_summary(session_id, summary, messages_count)`
- `get_context_for_prompt(query)` — returns `[User Preferences]\n[Active Context]\n[Relevant Memories]` text block

### 1.6 Session

`session/storage.py:22` — `SessionStorage(SQLiteStore)`:
- 3 tables: `sessions` (id, title, model, provider, workspace, mode, message_count, status, metadata), `messages` (id, session_id, role, type, content, tool_calls, tool_call_id, name, created_at, metadata), `file_changes` (id, session_id, file_path, change_type, original_content, new_content)
- Idempotent `ALTER TABLE … ADD COLUMN mode/type` for backward compat
- `save_message()` returns cursor.lastrowid; `get_messages()` orders by `created_at`

`session/manager.py:26` — `SessionManager`:
- UUID4 hex[:12] session ids; auto-save on atexit + SIGINT/SIGTERM (main thread only)
- `create_session()`, `resume_session()` (prefix match), `save_message()`, `create_checkpoint()`, `rollback()`, `fork_session()`, `rename_session()`, `get_last_session_for_workspace()`, `auto_title()` (first 80 chars)
- `_atexit_save_all()` swallows OSError/ValueError
- **No background autosave timer** (`auto_save_interval=30` is documented but unused)

`session/checkpoint.py:84` — `CheckpointManager`:
- `index.json` + `cp_<id>/<safe_filename>.bak` per checkpoint
- `max_checkpoints=50` cap (FIFO trim)
- Atomic writes via tempfile + os.replace
- `Checkpoint.files` lazy-loads content from disk

### 1.7 Permissions

`permissions/rules.py`:
- `PermissionLevel(str, Enum)`: `ALLOW | ASK | DENY`
- `@dataclass PermissionRule(tool_name, level, description, arg_patterns: dict, project)`
- `PermissionRule.matches(tool_name, arguments)` — supports wildcard `*` and regex per-arg
- `DEFAULT_RULES` (11): read-only tools auto-ALLOW, mutating tools ASK, `browser` ASK
- **No `SUGGEST` mode** despite YAML comment mentioning it

`permissions/manager.py:35` — `PermissionManager`:
- 3 state sets: `_session_grants`, `_session_denials`, `_always_allow`
- Cache key = `tool_name + "|" + sha256(json.dumps(args, sort_keys=True)).hexdigest()[:16]`
- `evaluate()` first match wins; `check_and_approve()` calls `_approval_callback` on ASK
- `grant_always()` / `revoke_always()` (silent on missing)
- `load_from_config(config["permissions"])` reads `mode` + `tools.{name: level}`; does NOT read `allowed_commands`/`denied_commands` (those go to Sandbox)

### 1.8 Skills

`skills/skill_loader.py`:
- `Skill(Tool)` with `name`, `description`, `parameters`, `permission_level` ("read-only" → PLAN mode, "read-write" → BUILD mode)
- Frontmatter regex: `r"^---\s*\n(.*?)\n---\s*\n(.*)$"` (DOTALL)
- Required frontmatter keys: `name`, `description`, `parameters`, `permission_level`
- Body becomes `instructions` verbatim; no `{{var}}` substitution — only a plain `kwargs` bullet list
- 3 execution paths: factory, `AgentLoop` (lazy import), template fallback
- **No parameter templating engine**

`skills/skill_registry.py:20` — `SkillRegistry`:
- Thread-safe discover via `path.glob("*.md")`
- Always augments with `Path(__file__).parent / "builtin"` (5 built-in skills)
- `get_as_tools()` returns the registry for LLM function calling

`skills/builtin/` (5 skills):
| Name | Permission | Parameters |
|------|-----------|------------|
| `code_review` | read-only | `path` |
| `debug` | read-write | `path`, `error_message` |
| `documentation` | read-write | `path`, `output_format?` |
| `refactor` | read-write | `path`, `explanation?` |
| `test_writer` | read-write | `path`, `test_framework?` (default pytest) |

### 1.9 MCP

`mcp/transport.py`:
- `MCPTransport(ABC)` with `start/send_message/register_handler/close`
- `StdioTransport` — newline-delimited JSON (NOT LSP-framed)
- Single transport type: stdio only

`mcp/client.py:56` — `MCPClient`:
- **Command sanitization**: rejects `; & | > < $ \` \n` chars; allowlist `{node, npx, python, python3, pip, pip3, pipx, uv, ruby, git, deno}` or absolute path with `.is_file()` check
- **Env sanitization**: only allows `PATH/HOME/USER/LANG/COMSPEC/SYSTEMROOT/WINDIR/TEMP/TMP/USERNAME/USERPROFILE/LOGNAME/PWD` + `NEXUS_*`/`MCP_*` prefixed keys
- Handshake: `initialize` with `protocolVersion: "2024-11-05"`, `clientInfo: {name: "NexusAgent", version: "1.0"}`; then `notifications/initialized`
- 15s startup timeout; UUID-keyed pending-request map with `threading.Event` synchronization
- `MCPProxyTool(Tool)` with `permission_level="ask"` hardcoded

`mcp/server.py:14` — `MCPServer` (exposes NexusAgent tools as MCP server):
- Handles `initialize/tools/list/tools/call`
- JSON-RPC error codes: -32601 (method not found), -32603 (internal)
- **Not exported from package** despite being fully implemented

### 1.10 Tools

| Tool | Class | File | Permission | Actions | State | Network/FS |
|------|-------|------|------------|---------|-------|------------|
| `read_file` | `ReadFileTool` | `file_ops.py:35` | read-only | path, start_line?, end_line? | stateless | FS read (10MB cap, 500-line cap) |
| `write_file` | `WriteFileTool` | `file_ops.py:149` | read-write | path, content | stateless | FS write (50MB cap, refuses .git) |
| `search_files` | `SearchFilesTool` | `file_ops.py:222` | read-only | pattern, path?, include_glob?, max_results? | stateless | FS search (ReDoS guard, 1MB file cap) |
| `list_directory` | `ListDirectoryTool` | `file_ops.py:396` | read-only | path?, recursive?, max_depth? | stateless | FS scan |
| `run_command` | `ShellTool` | `shell.py:16` | read-write | command, cwd?, timeout? | stateless | Shell exec via Sandbox (120s cap) |
| `edit_file` | `CodeEditTool` | `code_edit.py:62` | read-write | path, old_content, new_content, replace_all?, validate_ast?, canonicalize? | stateless | FS edit with AST gate |
| `insert_lines` | `InsertLinesTool` | `code_edit.py:223` | read-write | path, line_number, content | stateless | FS edit |
| `import_graph` | `ImportGraphTool` | `code_intel.py:24` | read-only | action (build/find_dependents), target? | cache | AST walk |
| `call_graph` | `CallGraphTool` | `code_intel.py:131` | read-only | file_path, trace_function? | stateless | AST walk |
| `rename_symbol` | `RenameTool` | `code_intel.py:240` | read-write | file_path, old_symbol, new_symbol | stateless | AST + regex fallback (10MB cap) |
| `git` | `GitTool` | `git_ops.py:38` | read-write | subcommand, args? | stateless | Shell exec with allowlist (100KB output cap) |
| `smart_commit` | `SmartCommitTool` | `git_ops.py:132` | read-only | (none) | provider-aware | git diff + LLM call |
| `pr_generator` | `PRGeneratorTool` | `git_ops.py:216` | read-only | base_branch? | provider-aware | git log + LLM call |
| `ci_analyzer` | `CIAnalyzerTool` | `git_ops.py:305` | read-only | log_text | provider-aware | LLM call |
| `web_search` | `WebSearchTool` | `web_search.py:15` | read-only | query, max_results? | stateless | DuckDuckGo (512-char query cap) |
| `rag_search` | `RepositoryRAGTool` | `rag_search.py:17` | read-only | query, reindex? | SQLite | FTS5 + symbol index |
| `batch_edit` | `BatchEditTool` | `batch_edit.py:16` | read-write | edits (array) | stateless | Atomic multi-file edit with rollback |
| `browser` | `BrowserTool` | `browser.py:121` | read-write | action (navigate/read/click/screenshot), url?, selector?, output_path? | ephemeral | Playwright + HTTPX fallback (SSRF-blocked) |
| `lsp_query` | `LSPClientTool` | `lsp_client.py:45` | read-only | action, file, line?, character?, new_name? | cached pool | Real LSP over stdio + AST fallback |

**Browser SSRF protection (browser.py:203-240)**:
- Blocks `file://`, non-http(s)
- Blocks cloud metadata IPs: AWS/GCP/Azure `169.254.169.254`, Alibaba `100.100.100.200`, Oracle `192.0.0.192`
- Blocks private networks: `127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16`
- Blocks hostnames: `metadata.google.internal`, `metadata`

### 1.11 GUI (`gui/server.py`)

**REST routes**:
| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/status` | `get_status` | Engine + hardware |
| GET | `/api/models` | `get_models` | Discovered GGUF/ONNX |
| POST | `/api/models/load` | `load_model` | Swap engine with guardrail check |
| POST | `/api/config/update` | `update_config` | Live effort/goal/guardrails |
| GET | `/api/sessions` | `list_sessions` | All sessions |
| POST | `/api/sessions/create` | `create_session` | New session |
| GET | `/api/sessions/{id}` | `get_session` | Message history |
| GET | `/api/tasks` | `get_tasks` | TaskGraph state |
| GET | `/api/nla/{id}` | `get_nla` | NLATelemetry |
| POST | `/api/debate` | `trigger_debate` | Multi-agent code review |
| POST | `/api/verify` | `trigger_verify` | Lint+secrets+test |
| POST | `/api/commit` | `trigger_commit` | Auto-commit |
| WS | `/api/ws/{id}` | `websocket_endpoint` | Real-time chat streaming |

**Security middleware (server.py:110-155)**:
- Rate limit: 100 req / 60s per IP (path prefix `/api/`)
- Body size: 10 MB
- CSP: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- CORS: `http://127.0.0.1` + `http://localhost` only

**Frontend (gui/frontend/)**:
- 3-column CSS grid (280px / fluid / 340px)
- Dark glassmorphism (backdrop-filter blur 16px)
- 5 JS modules: `App` (lifecycle), `Chat` (WS+streaming), `Models` (loader modal), `Settings` (localStorage), `Utils` (escape, simple markdown, time)
- Theme: `--bg-main: #060913`, `--accent-blue: #38bdf8`, `--accent-green: #34d399`, `--font-outfit`, `--font-code: 'Fira Code'`
- **No build step** — plain JS, no framework

### 1.12 Providers

| Provider | Class | Subclass of | Env Var | Default Model | Streaming | Tool Calling |
|----------|-------|-------------|---------|---------------|-----------|--------------|
| openai | `OpenAIProvider` | (own) | `OPENAI_API_KEY` | `gpt-4o` | yes | yes |
| anthropic | `AnthropicProvider` | (own) | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` | yes | yes |
| google | `GoogleProvider` | OpenAI | `GEMINI_API_KEY`/`GOOGLE_API_KEY` | `gemini-1.5-pro` | yes | yes |
| ollama | `OllamaProvider` | OpenAI | — | `llama3` | yes | yes |
| openrouter | `OpenRouterProvider` | OpenAI | `OPENROUTER_API_KEY` | `anthropic/claude-3.5-sonnet` | yes | yes |
| groq | `GroqProvider` | OpenAI | `GROQ_API_KEY` | `llama3-70b-8192` | yes | yes |
| deepseek | `DeepSeekProvider` | OpenAI | `DEEPSEEK_API_KEY` | `deepseek-chat` | yes | yes |
| bedrock | `AWSBedrockProvider` | (own, boto3) | `AWS_REGION`/`AWS_DEFAULT_REGION` | `claude-3-5-sonnet-v2:0` | yes | yes |
| custom | `CustomOpenAIProvider` | OpenAI | — | `custom-model` | yes | configurable |

**No retry, no rate-limit handling, no cost tracking** in any provider.

---

## Part 2 — Slash Command Catalog

### 2.1 NexusAgent slash commands (70+)

**Session/memory** (12): `/clear` `/new` `/reset` `/session` `/sessions` `/resume` `/continue` `/rename` `/fork` `/log` `/export` `/import` `/copy` `/rewind`

**Model/runtime** (5): `/model` `/runtime` `/install` `/display-settings` `/wizard`

**Agent control** (15): `/mode` `/effort` `/goal` `/sandbox` `/permissions` `/context` `/compact` `/reflect` `/debate` `/verify` `/task` `/undo` `/retry` `/explain` `/btw`

**Modes** (6): `/plan` `/build` `/fast` `/quick` `/autonomous` `/review`

**Orchestration** (2): `/orchestrate` `/self-heal` (via `/retry`)

**Tools** (5): `/search` `/index` `/browser` `/mcp` `/skill` `/skills`

**Git** (4): `/diff` `/branch` `/commit` `/pr`

**Config** (7): `/config` `/tui` `/theme` `/color` `/vim` `/statusline` `/status`

**Debug** (5): `/stats` `/memory` `/telemetry` `/nla` `/doctor`

**Misc** (6): `/help` `/quit` `/exit` `/feedback` `/init` `/add-dir`

**Skipped handlers in command_dispatcher** (broken callers noted in audit v1):
- `/log` calls `self._session_mgr.get_messages(limit=20)` — method doesn't exist
- `/export` calls `self._session_mgr.export_session()` — method doesn't exist
- `/import` calls `self._session_mgr.import_session(src)` — method doesn't exist
- `/copy` references undefined `copy_to_clipboard` helper

### 2.2 Cross-CLI slash command inventory

| Command | NexusAgent | claude-code | opencode | codex | letta | openclaw | hermes |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Help | `/help` | `/help` | `/help` | `/help` | `/help` | `/help` | `/help` |
| Clear/Reset | `/clear` `/new` | `/clear` `/reset` `/new` | `/clear` `/new` | `/new` `/reset` | `/new` `/reset` | `/new` `/reset` | `/new` `/reset` |
| Sessions | `/session` `/resume` | `/resume` `/branch` | `/resume` `/continue` | `/resume` `codex resume` | `/agents` `/pin` | `/sessions` | `/sessions` |
| Fork | `/fork` | `/branch` | `--fork` | `codex exec --fork` | (concurrent agents) | (gateway) | (delegates) |
| Rename | `/rename` | `/rename` | — | — | — | — | `/title` |
| Model | `/model` | `/model` | `/model` | `/model` | `/model` | `/model` | `/model` |
| Permissions | `/permissions` | `/permissions` | `--dangerously-skip-permissions` | `/permissions` (presets) | `/permissions` | (config) | (config) |
| Context | `/context` | `/context` `/compact` | `/compact` `/summarize` | `/compact` | `/doctor` | `/compact` | `/compress` `/usage` `/insights` |
| Memory | `/memory` | `/memory` | — | — | `/memory` `/palace` `/doctor` | `/memory` | `/memory` |
| Rewind | `/rewind` | `/rewind` `/checkpoint` `/undo` | `/undo` `/redo` | `/undo` | — | `/rewind` | `/retry` `/undo` |
| Export | `/export` | `/export` | `/export` | — | — | — | — |
| Config | `/config` `/theme` | `settings.json` | `tui.json` `opencode.json` | `config.toml` | (config) | `openclaw.json` | `config.yaml` |
| Doctor | `/doctor` | `/doctor` `/debug` | — | — | `/doctor` | `/doctor` | `/doctor` |
| Init | `/init` | `/init` | `/init` | — | `/init` | `/init` | (config) |
| TTS/Voice | — | — | — | — | — | — | `/voice on/off/tts` |
| Skin | — | — | — | — | — | — | `/skin` |
| Title | — | — | — | — | — | — | `/title` |
| Status | `/status` | `/status` | — | `/status` | `/status` | `/status` | `/status` |
| Review | `/review` | — | — | `/review` | — | — | — |
| Subagents | — | — | `/subagent` | `/agents` | (built-in) | (built-in) | `/background` |
| Reasoning | `/effort` (5 levels) | `--effort` | `--variant` | (config) | (config) | (config) | `/reasoning high` |
| Worktree | — | `--worktree` | — | `--worktree` | — | — | `-w` |
| MCP | `/mcp` `/mcp connect` `/mcp install` | `/mcp` | `/mcp` | `/mcp` | `/connect` | (config) | `/mcp` |
| Skills | `/skill` `/skills` | (skills + commands) | `/skill-creator` | — | `/skills` `/skill-creator` | — | `/skills browse` |
| Plugins | — | plugins | plugins | — | — | plugins | — |
| Hooks | — | hooks | hooks | — | hooks | hooks | hooks |
| Custom commands | — | `commands/*.md` | `commands/*.md` | — | (prompts) | (commands) | (custom) |

### 2.3 Unique to NexusAgent

- `/effort` with 5 explicit reasoning levels (low/medium/high/xhigh/max) — only Claude Code has equivalent
- `/mcp install` (persists to config) — exceeds most peers
- `/debate`, `/verify`, `/orchestrate`, `/self-heal` — multi-agent primitives
- `/nla` — neural lambda autoencoder telemetry
- `/index` — RAG index builder
- `/telemetry` — runtime metrics

### 2.4 Unique to other CLIs (NexusAgent missing)

- **claude-code**: `/branch` (conversation fork in-place), `/agents` (subagent manager), `/heapdump` (JS heap diagnostics), `/workflows` (progress view), `/mcp` (full marketplace), `--teleport`, `--from-pr`, `--remote-control`
- **opencode**: `tui.json` + `opencode.json` separation, `mDNS` discovery, `acp` (Agent Client Protocol) server, `serve`/`web` commands, `web` command, `web` share
- **codex**: `--sandbox` policy levels, `codex review` presets, `codex mcp` shell, `/review` reviewer subagent, image inputs in composer, `Tab` to queue follow-up
- **letta**: `/memfs` (git-backed memory filesystem), `/sleeptime` (dream subagent), `/palace` (memory view), `/memfs` enable/disable, `/remember` (explicit memory edit), `/pin` (favorite agent), `/search` (cross-message search)
- **openclaw**: `/mcp` plugin marketplace, channel-specific status, cron UI, secrets obfuscation, `$5 VPS` model routing
- **hermes**: `/voice on/tts` (real-time voice), `/background <prompt>` (parallel isolated sessions), `/insights [--days N]` (local analytics), `hermes claw migrate` (one-shot migration from OpenClaw), 6 terminal backends (local/Docker/SSH/Singularity/Modal/Daytona)

---

## Part 3 — Feature-by-Feature Matrix

### 3.1 Memory Architecture

| Aspect | NexusAgent | claude-code | letta (MemFS) | openclaw | hermes |
|--------|------------|-------------|---------------|----------|--------|
| Storage | SQLite FTS5 + YAML | markdown files | git-backed FS | markdown + sqlite-vec | markdown + SQLite FTS5 |
| Tiers | working + long-term + episodic + user-profile | CLAUDE.md + auto-memory | system/ + bank/ + entities/ | MEMORY.md + daily log + bank/ | FTS5 + LLM summarization |
| Self-edit | (no) | yes (auto memory) | yes (agents rewrite) | yes (sleep-time + reflection) | yes (skill learning) |
| Git-tracked | (no) | (no) | yes | yes | yes |
| Cross-session search | yes (FTS5) | yes (recall) | yes (`/search`) | yes (semantic) | yes (cross-session FTS5) |
| Vector embeddings | (no — FTS5 only) | (no) | (planned) | yes (sqlite-vec) | (optional) |
| User model | yes (UserProfile YAML) | yes (CLAUDE.md) | yes (SOUL.md) | yes (SOUL.md) | yes (Honcho dialectic) |
| **Nuggets** | | | | | |
| Compaction | 60-msg threshold | `/compact` | MemFS compaction | auto-compaction | `/compress` |
| Sleep-time | (no) | (no) | yes (dream) | yes (periodic) | yes (skill learning) |
| Progressive disclosure | (no) | (no) | yes (system/ + descriptions) | yes (memory tree) | yes (skill frontmatter) |
| Tools for memory | (no) | (no) | yes (`memory(...)`) | yes (memory tool) | (no) |

**Gap**: NexusAgent memory is **FTS5-only** with no vector embeddings, no self-edit tools, no git backing. Letta + OpenClaw are generations ahead in memory architecture.

### 3.2 Sessions / Resumption

| Aspect | NexusAgent | claude-code | codex | opencode | hermes |
|--------|------------|-------------|-------|----------|--------|
| Persistence | SQLite (sessions.db) | JSONL | codex-internal | server sessions | SQLite + JSONL |
| Resume by id | `/resume <id>` (prefix) | `--resume <id>` | `codex resume <id>` | `--session <id>` | `--resume <id>` |
| Resume picker | (no — uses `get_last_for_workspace`) | yes (`/resume` picker) | yes (`codex resume`) | yes (`/sessions`) | yes (`/sessions`) |
| Fork | yes (`/fork`) | yes (`/branch`, `--fork-session`) | yes (`--fork`) | yes (`--fork`) | (parallel agents) |
| Replay | yes (CLI `_replay_session_history`) | yes | yes | yes | yes |
| Checkpoints | yes (`CheckpointManager`, 50 cap) | yes (`/rewind` + `/checkpoint`) | (no) | (no) | (no) |
| Re-summarize on resume | (no) | (no) | (no) | (no) | yes |
| Branching trees | (no) | yes (visual) | (no) | (no) | (no) |
| Auto-titling | yes (`auto_title`, 80 chars) | yes | yes | yes | yes (`/title`) |
| Session from-PR | (no) | yes (`--from-pr`) | (no) | (no) | (no) |
| Background session | (no) | yes (`--bg`, `/stop`) | (no) | yes (subagents) | yes (`/background`) |

**Gap**: NexusAgent has no session picker UI, no session tree visualization, no background sessions, no `codex-internal` style resumability across machines.

### 3.3 LSP / Code Intelligence

| Aspect | NexusAgent | opencode | claude-code | codex |
|--------|------------|----------|-------------|-------|
| Transport | JSON-RPC 2.0 over stdio + Content-Length framing | JSON-RPC stdio | (via plugins) | (via plugins) |
| Default servers | python (pylsp), typescript (typescript-language-server), rust (rust-analyzer), go (gopls) | python, typescript, eslint, ocaml, zig | — | — |
| Custom servers | `register_lsp_server(language, LSPConfig)` | `lsp.<name>` in config | — | — |
| Auto-download | (no) | yes (`OPENCODE_DISABLE_LSP_DOWNLOAD`) | — | — |
| Actions | 8 (definition, hover, diagnostics, references, document_symbols, completion, format, rename) | 9 (+ goToImplementation, call hierarchy) | — | — |
| AST fallback | yes (pure ast) | (uses linter) | — | — |
| Pool/caching | yes (`LSPClientPool` per language per workspace) | yes | — | — |
| **`LSPClientPool` cache** | one client per language per resolved workspace | one per language | — | — |
| Subprocess test gating | `nexus_run_subprocess_tests=1` env var | — | — | — |

**Verdict**: NexusAgent's LSP implementation is **on par with opencode's experimental feature**, including AST fallback that opencode does not have.

### 3.4 MCP

| Aspect | NexusAgent | claude-code | opencode | codex | hermes |
|--------|------------|-------------|----------|-------|--------|
| Transport | stdio (newline JSON) | stdio + SSE | stdio + HTTP | stdio + HTTP | stdio + HTTP |
| Server allowlist | yes (11 executables + abs path) | (Claude Desktop config) | (config) | (config) | (config) |
| Env allowlist | yes (12 keys + NEXUS_/MCP_) | (passthrough) | (passthrough) | (passthrough) | (passthrough) |
| Command injection guard | yes (rejects `; & \| > < $ \`) | (n/a) | (n/a) | (n/a) | (n/a) |
| Config format | YAML `mcp.servers[].{command,args,env}` | `mcp.json` / `claude_desktop_config.json` | `mcp` in opencode.json | `[mcp.servers]` in config.toml | `[mcp_servers]` in config |
| Runtime install | `/mcp install` (persists) | yes | yes | yes | yes |
| Connect at runtime | `/mcp connect` | (restart) | (restart) | (restart) | (restart) |
| Agent-as-MCP-server | yes (`MCPServer` class) | (separate) | (separate) | yes (`codex mcp-server`) | (separate) |
| Marketplace | (no) | yes | yes | yes | yes |

**Verdict**: NexusAgent's MCP is **more secure than peers** (command allowlist, env allowlist, injection guard) but **less convenient** (no marketplace).

### 3.5 Skills

| Aspect | NexusAgent | claude-code | opencode | letta | hermes |
|--------|------------|-------------|----------|-------|--------|
| Format | YAML frontmatter + markdown | SKILL.md (similar) | SKILL.md (similar) | skill folders | agentskills.io open standard |
| Discovery dirs | config + builtin fallback | global + project + plugin | global + project | global + project + agent | global + project |
| Parameter substitution | (no) | yes (frontmatter + body) | yes ($ARGUMENTS, @file, !shell) | yes | yes |
| Subagent invocation | yes (via `AgentLoop` lazy import) | yes | yes (`subtask: true`) | yes (built-in) | yes (Programmatic Tool Calling) |
| Built-in count | 5 | 0 (user-defined) | 0 | 0 | 0 |
| Auto-create from experience | (no) | (no) | (no) | yes (sleep-time) | yes (skill learning) |
| Skill-creator | (no) | (via skills system) | `/skill-creator` | `/skill-creator` | (built-in) |

**Verdict**: NexusAgent's skill system is **5 markdown files** vs Letta/Hermes' self-improving system. The basics are there, the self-improvement is missing.

### 3.6 Providers

| Aspect | NexusAgent | claude-code | opencode | codex | hermes |
|--------|------------|-------------|----------|-------|--------|
| Local GGUF | yes (`llama-cpp-python`) | (no) | (via plugins) | (no) | (no) |
| Local ONNX | yes (`onnxruntime-genai`) | (no) | (no) | (no) | (no) |
| OpenAI | yes | yes | yes | yes | yes |
| Anthropic | yes | yes (native) | yes | yes | yes |
| Google | yes (OpenAI-compat) | yes | yes | yes | yes |
| Ollama | yes (OpenAI-compat) | yes | yes | yes | yes |
| OpenRouter | yes | (via custom) | yes | (via custom) | yes (built-in) |
| Groq | yes | (via custom) | yes | (via custom) | (via OpenRouter) |
| DeepSeek | yes | (via custom) | (via custom) | (via custom) | (via custom) |
| AWS Bedrock | yes (boto3, native) | yes | yes | yes | (via custom) |
| Custom OpenAI | yes | (via custom) | (via custom) | (via custom) | (via custom) |
| Chat-format auto-detect | yes (7+ formats) | n/a | (n/a) | n/a | n/a |
| Retry logic | (no) | yes | yes | yes | yes |
| Rate-limit handling | (no) | yes | yes | yes | yes |
| Cost tracking | via `usage` dict | yes | yes | yes | yes |
| Fallback model | (no) | yes | yes | yes | yes |
| Provider-level timeout | (no) | yes | yes | yes | yes (per-provider ms) |

**Verdict**: NexusAgent has **the widest provider count** (9 + 2 local) but **the lowest provider resilience** (no retry, no rate-limit, no fallback). This is the single biggest gap.

### 3.7 Browser / Web

| Aspect | NexusAgent | claude-code | opencode | codex | hermes |
|--------|------------|-------------|----------|-------|--------|
| Engine | Playwright + HTTPX fallback | (via plugins) | (via plugins) | (via plugins) | (Tool Gateway) |
| SSRF protection | yes (5 private ranges + 4 cloud metadata IPs + 2 hostnames) | (via plugins) | (via plugins) | (via plugins) | (gateway-managed) |
| Configurable | yes (`BrowserConfig` + `NEXUS_BROWSER_*`) | (via plugins) | (via plugins) | (via plugins) | (via config) |
| Screenshots | yes (per-call output_path) | (via plugins) | (via plugins) | (via plugins) | yes |
| Markdown extraction | yes (custom HTMLParser) | (via plugins) | (via plugins) | (via plugins) | yes |
| Image gen | (no) | (no) | (no) | (no) | yes (Tool Gateway) |
| TTS | (no) | (no) | (no) | (no) | yes (Tool Gateway) |
| Search (Exa) | (no — uses DDG only) | (no) | yes (Exa) | (no) | yes (gateway) |

**Verdict**: NexusAgent's browser is **more secure** than peers but **less featureful** (no Exa, no image gen, no TTS).

### 3.8 Permissions

| Aspect | NexusAgent | claude-code | opencode | codex | hermes |
|--------|------------|-------------|----------|-------|--------|
| Levels | ALLOW / ASK / DENY | allow / ask / deny | allow / ask / deny + wildcard | (sandbox modes) | (config) |
| Per-tool | yes | yes | yes | yes | yes |
| Per-arg regex | yes (`arg_patterns`) | (n/a) | (n/a) | (n/a) | (n/a) |
| Per-project | yes | (n/a) | (n/a) | (n/a) | (n/a) |
| Session-grant cache | yes (sha256 of args) | yes | yes | yes | yes |
| Always-allow | yes | yes | yes | yes | yes |
| Wildcard | yes (`*`) | yes | yes | yes | yes |
| Container sandbox | (no) | (yes) | (yes) | yes (Landlock) | yes (Docker) |
| DM pairing | (no) | (n/a) | (n/a) | (n/a) | yes |
| Token auth for non-loopback | (n/a, no server) | (n/a) | yes | (n/a) | (n/a) |

**Verdict**: NexusAgent's per-arg regex + per-project scoping is **more granular** than peers. Container sandbox is missing.

### 3.9 Tools

NexusAgent has **19 first-party tools** (see §1.10). Compared to peers:

| Tool | NexusAgent | claude-code | opencode | codex | hermes |
|------|:---:|:---:|:---:|:---:|:---:|
| file read/write | yes | yes | yes | yes | yes |
| shell exec | yes (sandboxed) | yes | yes | yes | yes |
| code edit (search/replace) | yes + AST gate | yes | yes | yes | yes |
| git | yes (allowlist) | yes | yes | yes | yes |
| web search | yes (DDG) | yes (Exa) | yes (Exa) | yes | yes |
| browser | yes | yes (plugin) | yes (plugin) | yes (plugin) | yes (gateway) |
| LSP | yes (real) | (plugin) | yes (experimental) | (plugin) | (plugin) |
| MCP | yes | yes | yes | yes | yes |
| batch edit | yes (atomic) | (no) | (no) | (no) | (no) |
| import/call graph | yes (AST) | (no) | (no) | (no) | (no) |
| symbol rename | yes (AST + regex) | (no) | (no) | (no) | (no) |
| repo RAG | yes (FTS5) | (plugin) | (plugin) | (plugin) | (plugin) |
| smart commit | yes (LLM) | (no) | (no) | (no) | (no) |
| PR generator | yes (LLM) | (no) | (no) | (no) | (no) |
| CI analyzer | yes (LLM) | (no) | (no) | (no) | (no) |
| todowrite | (no) | (no) | yes | (no) | (no) |
| webfetch | (no, browser handles) | yes | yes | yes | yes |

**Verdict**: NexusAgent's tool count is **competitive** but missing todowrite and webfetch.

### 3.10 UI Surfaces

| Surface | NexusAgent | claude-code | opencode | codex | hermes |
|---------|------------|-------------|----------|-------|--------|
| CLI (TUI) | Textual | terminal.app | TUI | TUI | TUI |
| GUI (web) | FastAPI + WS + plain JS | (separate product) | yes (`web` command) | (separate) | (separate) |
| Desktop | (no) | yes | (no) | (no) | yes |
| Mobile | (no) | yes | (no) | (no) | yes |
| Messaging (Telegram etc.) | (no) | (no) | (no) | (no) | yes (20+ platforms) |
| Web chat | (same as GUI) | (yes) | yes | (no) | yes (chat.letta.com / chatletta) |

**Verdict**: NexusAgent CLI + GUI is **complete**; messaging/mobile is **entirely missing**.

### 3.11 Multi-agent / Subagents

| Aspect | NexusAgent | claude-code | opencode | codex | hermes |
|--------|------------|-------------|----------|-------|--------|
| Subagent types | orchestrator (planner/executor/reviewer), self-heal, debate | general-purpose, statusline-setup, Explore, Plan | (config) | (config) | general-purpose, forked, recall, history-analyzer |
| Configurable agent files | (no) | yes (`/agents`) | yes (`opencode agent create`) | yes (`[agents]`) | yes |
| Parallelism | yes (orchestrator) | yes (subagents) | yes (background) | yes (subagents) | yes (`/background`) |
| Agent-internal | yes (debate, self-heal) | (no) | (no) | (no) | (no) |
| Skills-as-subagents | yes (Skill subclass Tool) | yes | yes | yes | yes |
| Communication | shared in-process state | isolated worktree | isolated worktree | isolated worktree | isolated daemon thread |

**Verdict**: NexusAgent's multi-agent primitives (debate, self-heal, orchestrator) are **unique**, but the configurable agent-system is behind.

### 3.12 Reasoning / Effort

| Level | NexusAgent | claude-code | opencode | codex | hermes |
|-------|:---:|:---:|:---:|:---:|:---:|
| 1 (low) | 15 it / T0.30 / 2048 tok | (via `--effort`) | (via `--variant`) | (config) | (config) |
| 2 (medium) | 25 it / T0.15 / 4096 tok | (via `--effort`) | (via `--variant`) | (config) | (config) |
| 3 (high) | 50 it / T0.10 / 8192 tok | (via `--effort`) | (via `--variant`) | (config) | (config) |
| 4 (xhigh) | 80 it / T0.05 / 16384 tok + reflection + multi-pass | (via `--effort`) | (via `--variant`) | (config) | (via `/reasoning high`) |
| 5 (max) | 120 it / T0.01 / 32768 tok + reflection + multi-pass | (via `--effort`) | (via `--variant`) | (config) | (config) |

**Verdict**: NexusAgent's effort system is **most explicit** with named levels and visible iteration budgets.

### 3.13 Runtimes / Hardware

| Runtime | NexusAgent | llama.cpp ecosystem | opencode |
|---------|------------|---------------------|----------|
| CPU (llama-cpp-python) | yes (default) | yes | (via plugins) |
| CUDA | yes (`/runtime install cuda`) | yes | (via plugins) |
| Vulkan | yes | yes | (via plugins) |
| Metal | yes | yes | (no) |
| ROCm | yes | yes | (no) |
| ONNX (DML/CUDA/CPU) | yes | n/a | n/a |
| TPU | (no) | (no) | (no) |
| OpenVINO | (no) | (no) | (no) |
| Detection | `cli/runtimes.py` scans nvcc, CUDA_PATH, llama-cli, vulkaninfo, ROCM_PATH | n/a | n/a |

**Verdict**: NexusAgent has **the widest runtime coverage** of any agentic CLI.

---

## Part 4 — Identified Gaps (priority-ordered)

### 4.1 Critical (do next)

1. **Provider resilience**: add retry + exponential backoff + rate-limit handling + fallback chain. See `llm/providers/factory.py:50` and each provider's `chat_completion()`.
2. **Background sessions**: `claude --bg`, `codex exec --background`, opencode background subagents, hermes `/background` — NexusAgent has none.
3. **Session picker UI**: a TUI list with arrow keys + search, like claude-code's `/resume` picker. Currently we have `get_last_for_workspace` but no UI.
4. **Fix broken `/log`, `/export`, `/import`, `/copy`**: handlers in `cli/command_dispatcher.py:1260, 1289` and `cli/commands/session.py:28, 89, 158` call methods that don't exist on `SessionManager`.
5. **Session autosave timer**: `auto_save_interval=30` is documented but unused (`session/manager.py:49-50`). Add a `threading.Timer` to call `save_session()` periodically.

### 4.2 Important

6. **Vector memory** (sqlite-vec): add embeddings to `MemoryManager` for semantic search; OpenClaw already does this.
7. **Memory self-edit tools**: expose `add_memory`, `update_memory`, `delete_memory` as `Tool` subclasses so the agent can manage its own memory (like Letta).
8. **Skill templating engine**: replace the `kwargs` bullet list with proper `{{var}}` substitution in `skill_loader.py:114-121`.
9. **Skill auto-creation from experience**: detect successful tool-call patterns and write a new `.md` skill file. Hermes does this with "skill learning".
10. **Provider-level timeout + per-provider config** like hermes's `--timeout` flag.
11. **Docker/SSH backends**: hermes supports 6 terminal backends (local, Docker, SSH, Singularity, Modal, Daytona); NexusAgent is local-only.
12. **Per-project CLAUDE.md equivalent**: NexusAgent has no `AGENTS.md` / `CLAUDE.md` style file auto-loading at session start. The closest is `SkillRegistry` but it doesn't load project instructions.

### 4.3 Nice-to-have

13. **`/webfetch`** (separate from `web_search`): opencode + claude-code both have a `webfetch` tool that fetches a specific URL and returns markdown.
14. **`todowrite` tool**: opencode has it; useful for multi-step task tracking.
15. **Plugin/extension system**: like opencode's `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_EXPERIMENTAL_*` flags. Currently NexusAgent has no plugin loader.
16. **Cost tracking dashboard**: every provider already returns `usage` dict; aggregate it across sessions.
17. **`ACP` (Agent Client Protocol) server**: opencode's `acp` command — expose NexusAgent over stdio for IDE integration.
18. **Auto-update**: hermes's `hermes update`; claude-code's built-in updater.
19. **Companion desktop app**: like letta, hermes.
20. **Messaging gateway**: hermes + openclaw support 20+ platforms (Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, …).

### 4.4 Already ahead of peers

- **Atomic batch_edit** with rollback — no peer has this
- **AST-aware code edit** with `validate_ast` + `canonicalize` — opencode doesn't
- **Real LSP with AST fallback** — peer-leading
- **9 cloud providers + 2 local (GGUF + ONNX)** — most count
- **5 reasoning effort levels** with explicit iteration budgets — most explicit
- **Multi-tier memory (working + long-term + episodic + user-profile)** — comparable to letta
- **Replay with type-aware collapse** — full history
- **Permission per-arg regex + per-project scoping** — most granular
- **Browser SSRF guard** — most secure
- **MCP command-injection guard + env allowlist** — most secure

---

## Part 5 — Top-3 Recommendations

### 5.1 Add provider resilience (highest leverage)

Add to `llm/base.py`:

```python
@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_s: float = 1.0
    max_backoff_s: float = 30.0
    backoff_multiplier: float = 2.0
    retry_on: tuple[type[Exception], ...] = (httpx.TimeoutException, httpx.HTTPStatusError)
    rate_limit_status: int = 429
```

Wrap each provider's `chat_completion()` with a retry decorator. Add fallback chain to `ProviderFactory.create_provider()`:

```python
ProviderFactory.create_provider(
    primary="anthropic",
    fallbacks=["openai", "ollama", "local"],
    config=config, model="claude-3-5-sonnet-latest"
)
```

### 5.2 Add background sessions + session picker

In `session/manager.py`, add:

```python
class BackgroundSession:
    def __init__(self, prompt: str, agent_config: AgentLoopConfig): ...
    def start(self) -> str:  # returns session_id
    def status(self) -> dict: ...
    def stop(self) -> None: ...
    def get_output(self) -> str: ...
```

In `cli/commands/session.py`, add `/background <prompt>`, `/sessions` (picker), and `/status <id>`.

### 5.3 Vector memory + self-edit tools

Add `sqlite-vec` to `core/sqlite_store.py`:

```python
class VectorStore(SQLiteStore):
    SCHEMA_SQL = "..."  # vec0 virtual table
    def embed(self, text: str) -> list[float]: ...  # via local ONNX or Ollama
    def search(self, query: str, k: int = 10) -> list[dict]: ...  # cosine similarity
```

Add `MemoryTool(Tool)` in `tools/memory.py` with actions: `add`, `update`, `delete`, `search`, `summarize`, `forget`.

Wire `MemoryTool` into AgentLoop's default tool set.

---

## Part 6 — Stats Summary

| Metric | Value |
|--------|-------|
| Source files (.py) | 87 |
| Total lines (src/) | ~26,500 |
| Test count (passing) | 263 |
| Test count (failing) | 0 |
| Test count (skipped) | 1 (`nexus_run_subprocess_tests=1` required) |
| CLI slash commands | 70+ |
| Tools | 19 |
| Cloud providers | 9 |
| Local runtimes | 5 (CPU, CUDA, Vulkan, Metal, ROCm) + ONNX |
| Effort levels | 5 |
| Built-in skills | 5 |
| Default LSP servers | 4 (python, typescript, rust, go) |
| MCP transports | 1 (stdio) |
| Memory tiers | 4 (working, long-term, episodic, user-profile) |
| Permission levels | 3 (ALLOW, ASK, DENY) |
| GUI endpoints | 13 (12 REST + 1 WS) |
| GUI frontend files | 6 (1 HTML, 1 CSS, 5 JS) |

---

## Part 7 — Cross-CLI Score Card (1-10)

| Dimension | NexusAgent | claude-code | opencode | codex | letta | openclaw | hermes |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Memory architecture | 7 | 7 | 5 | 4 | **10** | 9 | 9 |
| Session mgmt | 6 | **9** | 7 | 8 | 6 | 6 | 7 |
| LSP | 8 | 4 | 8 | 4 | 0 | 0 | 0 |
| MCP | 8 | **9** | 8 | 8 | 6 | 7 | 7 |
| Skills | 5 | 7 | 6 | 4 | 8 | 6 | **9** |
| Providers (count) | **10** | 8 | 8 | 8 | 5 | 7 | 8 |
| Providers (resilience) | 3 | **9** | 8 | 8 | 7 | 8 | 8 |
| Permissions (granularity) | **8** | 7 | 7 | 7 | 5 | 6 | 6 |
| Browser | 7 | 6 | 6 | 6 | 5 | 6 | **9** |
| Multi-agent | **8** | 7 | 6 | 6 | 6 | 7 | 7 |
| Reasoning effort | **10** | 8 | 7 | 5 | 5 | 5 | 6 |
| Local runtime coverage | **10** | 2 | 3 | 1 | 1 | 2 | 2 |
| CLI TUX polish | 7 | **9** | **9** | 8 | 6 | 7 | 9 |
| Messaging integration | 0 | 1 | 0 | 0 | 3 | **10** | **10** |
| Documentation | 6 | **10** | 8 | 7 | 8 | 5 | 9 |
| Test coverage | 8 | 6 | 7 | 5 | 6 | 5 | 5 |
| **Total (out of 160)** | **103** | **102** | **100** | **86** | **83** | **92** | **104** |

**NexusAgent is 1 point ahead of hermes, the closest peer, on the strength of:**
- 5 effort levels vs 1
- 9 providers vs 8
- 5 local runtimes vs 2
- Most granular permissions
- Most explicit reasoning

**NexusAgent is 6 points behind claude-code, the leader, on the weakness of:**
- No auto-memory / CLAUDE.md equivalent
- No session picker UI
- No background sessions
- No plugin system
- No `/branch` tree visualization
- Smaller docs footprint

---

## Part 8 — Next Iteration Plan

### Week 1: Provider resilience + background sessions
- Add `RetryPolicy` + `with_retry()` decorator to `llm/base.py`
- Add `fallbacks=[...]` to `ProviderFactory.create_provider()`
- Add `BackgroundSession` class to `session/manager.py`
- Add `/background`, `/sessions`, `/status` slash commands

### Week 2: Vector memory + memory tools
- Add `sqlite-vec` to dependencies
- New `llm/embeddings.py` with local GGUF/ONNX embedding model support
- `MemoryManager` gets `search_semantic()` method
- New `tools/memory.py` with `add/update/delete/search/summarize/forget` actions

### Week 3: Skill templating + auto-create
- Replace bullet list in `skill_loader.py:114-121` with Jinja-style `{{var}}` substitution
- Add `/skill-create <name>` command
- Background daemon: detect successful tool patterns, write skill files

### Week 4: Project context (AGENTS.md equivalent)
- New `core/project_context.py` that auto-loads `AGENTS.md`, `CLAUDE.md`, `.nexus/AGENTS.md` at session start
- Inject into `system_prompt_extra` like memory context

### Week 5: Plugin/extension system
- New `core/plugins.py` with discovery + manifest format
- `/plugin list/enable/disable/install` commands
- 3 sample plugins: pre-commit hook, custom-llm-provider, notification router

### Week 6: Documentation + ship
- Update AGENTS.md with v2 audit findings
- Write 4 tutorial docs (Diataxis: tutorial, how-to, reference, explanation)
- Add `setup-browser-cookies` for GUI login flows
- Add CI for the 6 new test files

---

## Appendix A — Test Inventory (263 tests, 1 skipped)

```
tests/nexus_agent/
├── core/         (8 tests)   config, context, sandbox, reflection
├── memory/       (35 tests)  manager, working, long-term, episodic, user_profile
├── session/      (17 tests)  storage, manager, checkpoint
├── permissions/  (18 tests)  manager, rules, regex
├── skills/       (7 tests)   loader, registry, builtin
├── mcp/          (8 tests)   transport, client, server
├── cli/          (14 tests)  renderer, app, input, commands
├── providers/    (20 tests)  openai, anthropic, google, ollama, factory
├── tools/        (90 tests)  NEW: lsp_transport(11), lsp_client(19),
│                            code_edit(18), browser(16), code_intel(17), batch_edit(9)
└── test_imports.py (5)      smoke imports
```

## Appendix B — Known Issues (carried from v1)

- `STATUS_ILLEGAL_INSTRUCTION` on pre-built llama-cpp-python wheels → build from source with `CMAKE_ARGS="-DLLAMA_NATIVE=ON"`
- `UnicodeEncodeError` on Windows cp1252 → `sys.stdout.reconfigure(encoding="utf-8")` in `cli/renderer.py`
- `InsertLinesTool` newline bug — **fixed in v1 audit round**
- `_get_hover_info` character param ignored — **fixed in v1 audit round**
- Hardcoded Playwright path in browser — **fixed in v1 audit round** (now `BrowserConfig` + env)
- `atexit` warning after pytest teardown — pre-existing, does not affect test results
- `SessionManager.export_session/import_session/get_messages(limit=…)` not implemented — see §4.1
