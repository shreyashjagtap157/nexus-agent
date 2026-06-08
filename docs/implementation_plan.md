# Nexus CLI — Complete Implementation Plan

> **Date:** June 8, 2026
> **Status:** Phase 1a ✅ Complete | Phase 1b 🔜 Next
> **Architecture:** Hybrid Rust/Python (Rust CLI/TUI, Python agents/memory/tools)

---

## Current State

### ✅ Phase 1a — Rust CLI Wrapper (Complete)

| Component | Files | Lines | Status |
|-----------|-------|-------|--------|
| Cargo.toml | `nexus-rs/Cargo.toml` | ~30 | ✅ clap, serde, tokio, tracing, thiserror |
| CLI Entry | `nexus-rs/src/main.rs` | ~300 | ✅ clap CLI (chat/doctor/version), ACP event loop |
| IPC Protocol | `nexus-rs/src/ipc/protocol.rs` | ~140 | ✅ ACP message types (JSON-RPC 2.0) |
| ACP Client | `nexus-rs/src/ipc/acp_client.rs` | ~140 | ✅ Async I/O, background reader, mpsc channel |
| Process Mgr | `nexus-rs/src/ipc/process.rs` | ~160 | ✅ find_python, spawn, health check, shutdown |
| Python Backend | `src/nexus_agent/backend.py` | ~190 | ✅ Agent init, ACPServer, mock provider |
| Python CLI | `src/nexus_agent/__main__.py` | +15 | ✅ backend Click command |
| ACP Server | `src/nexus_agent/mcp/acp_server.py` | ~160 | ✅ Fixed event serialization (event.data) |
| .gitignore | `.gitignore` | +1 | ✅ nexus-rs/target/ |

**Verification:** cargo build ✅, 916 tests ✅, dry-run ✅, ACP tests 5/5 ✅

### Bug Fixes Applied During Phase 1a

1. ACP server event serialization: `event.content`/`event.status` → `event.data` (AgentEvent has `.data`)
2. AgentLoop constructor: fixed to `AgentLoop(provider=..., tools=..., config=AgentLoopConfig(...))`
3. MemoryManager/SessionManager: use `data_dir=` not `config=`
4. Pipe deadlock: Python stderr `inherit()` not `piped()`
5. Shutdown: wait first, kill on timeout (was sending SIGKILL immediately)
6. `--provider` passthrough: forwarded from Rust CLI → Python backend
7. `init` handler added to ACP server
8. CodeEditTool import (was EditTool)
9. Config access pattern with `setdefault("agent", {})`

---

## Phase 1b — Ratatui TUI Shell

**Goal:** Replace the plain-text passthrough with a proper Ratatui terminal UI.

**Estimated effort:** ~1,200 lines of Rust, ~8-12 hours

### Module Structure

```
nexus-rs/src/
├── main.rs              ← Modified: wire TUI app instead of text loop
├── app.rs               ← NEW: App state machine (Model/Update/View + Bubbletea-style composability)
├── tui/
│   ├── mod.rs           ← Module declarations
│   ├── engine.rs        ← NEW: TUI engine (crossterm raw mode, event loop, 60fps render)
│   ├── layout.rs        ← NEW: Multi-pane layout engine (6 presets)
│   ├── chat_pane.rs     ← NEW: Streaming content display with block detection
│   ├── input_bar.rs     ← NEW: Prompt input with history
│   ├── status_bar.rs    ← NEW: Bottom status line (model, effort, tokens, time)
│   ├── task_inspector.rs ← NEW: Live task graph TUI panel
│   ├── resource_monitor.rs ← NEW: CPU/GPU/RAM live display
│   └── theme.rs         ← NEW: Theme system (TOML-defined, hot-reloadable)
├── cli/
│   ├── mod.rs           ← Module declarations
│   ├── app.rs           ← NEW: App state machine
│   └── commands.rs      ← NEW: Built-in command routing (no Python needed)
├── ipc/                 ← Existing (unchanged)
│   ├── mod.rs
│   ├── protocol.rs
│   ├── acp_client.rs
│   └── process.rs
└── config/
    ├── mod.rs           ← Module declarations
    ├── loader.rs        ← NEW: Load config from ~/.config/nexus/config.toml
    └── types.rs         ← NEW: Config type definitions
```

### File-by-File Specification

#### 1. Cargo.toml — Add Ratatui + crossterm dependencies

**What to add:**
```toml
# TUI
ratatui = "0.29"
crossterm = "0.28"
# Config
toml = "0.8"
directories = "6"
# Utilities (already have tracing, thiserror)
uuid = { version = "1", features = ["v4"] }
chrono = "0.4"
```

**Purpose:** Ratatui for immediate-mode terminal rendering, crossterm for keyboard/mouse input and raw mode.

#### 2. `tui/engine.rs` — TUI Engine (~200 lines)

**Responsibilities:**
- Enter/exit crossterm raw mode
- 60fps render loop with `ratatui::Terminal`
- Read keyboard events via crossterm
- Route events to App model
- Handle window resize
- Draw frame every 16ms

**Key functions:**
```rust
pub struct TuiEngine {
    terminal: Terminal<CrosstermBackend<Stdout>>,
    app: App,
}

impl TuiEngine {
    pub fn new(app: App) -> Result<Self>       // Enter raw mode, create terminal
    pub async fn run(&mut self, client: &mut AcpClient) -> Result<()>  // Main event loop
    pub fn draw(&mut self) -> Result<()>        // Render current frame
    fn handle_event(&mut self, event: Event, client: &mut AcpClient)  // Route events
}
```

**Event handling:**
- `KeyEvent { code: Up, Down }` → input history scroll
- `KeyEvent { code: Enter }` → send input as ACP prompt
- `KeyEvent { code: Char('c'), modifiers: CTRL }` → interrupt / "Cancel/continue/redirect"
- `KeyEvent { code: Char('p'), modifiers: CTRL }` → command palette
- `KeyEvent { code: Char('t'), modifiers: CTRL }` → toggle task inspector
- `KeyEvent { code: Char('l'), modifiers: CTRL }` → toggle layout
- `KeyEvent { code: Char('d'), modifiers: CTRL }` → quit
- `KeyEvent { code: Esc }` → close modal / cancel
- `KeyEvent { code: Tab }` → cycle focus between panes
- `KeyEvent { code: PageUp, PageDown }` → scroll chat pane

**Error handling:**
- If crossterm raw mode fails: fall back to Phase 1a text mode
- If render panics: restore terminal, print error, exit with code 1
- On Ctrl+C: send ACP interrupt notification, show dialog

#### 3. `tui/layout.rs` — Layout Engine (~150 lines)

**Responsibilities:**
- Define layout presets (Minimal, Developer, Researcher, Orchestrator, Monitor, Custom)
- Compute pane dimensions from terminal size
- Support horizontal/vertical splits with configurable ratios
- Manage pane visibility (toggle on/off)

**Data structures:**
```rust
enum LayoutPreset {
    Minimal,              // Single chat pane + status bar
    Developer,            // Chat + file diff side-by-side
    Researcher,           // Chat + memory browser + web results
    Orchestrator,         // Chat + agent graph + task inspector
    Monitor,              // Chat + resource monitor
    Custom(Vec<PaneSplit>),
}

enum PaneType {
    Chat,
    Diff,
    TaskInspector,
    MemoryBrowser,
    ResourceMonitor,
    AgentGraph,
}

struct PaneSplit {
    direction: Direction,  // Horizontal | Vertical
    ratio: f64,            // 0.0 - 1.0
    panes: Vec<PaneType>,
}

fn compute_layout(terminal_size: Size, preset: &LayoutPreset) -> Vec<PaneRect>
    // Returns list of (PaneType, Rect) for drawing
```

**Layout algorithms:**
- Minimal: chat = full width × (height - 1), status bar = full width × 1
- Developer: chat = 50% width, diff = 50% width, status bar = bottom
- Researcher: chat = 40% width, memory = 30% width, web = 30% width
- Orchestrator: chat = 40% width, task = 30% width, graph = 30% width
- Monitor: chat = 60% width, resource = 40% width

**Error handling:**
- Terminal too small (< 80×24): show warning overlay
- Invalid ratios (sum ≠ 1.0): normalize to equal distribution
- Custom layout parse failure: fall back to Minimal

#### 4. `tui/chat_pane.rs` — Streaming Content Display (~200 lines)

**Responsibilities:**
- Render streaming content chunks as they arrive from ACP
- Block detection: identify code blocks, prose, tool calls, errors
- Syntax highlighting for code blocks (basic keyword coloring)
- Line numbers for code blocks
- Scrollback buffer (10,000 lines max)
- Auto-scroll to bottom on new content

**Data structures:**
```rust
struct ChatPane {
    buffer: Vec<ContentBlock>,    // Render buffer (max 10,000)
    scroll_offset: usize,         // Current scroll position
    auto_scroll: bool,            // Follow new content
    streaming_buffer: String,     // In-progress content chunk
    current_block: Option<ContentBlockType>,
}

enum ContentBlock {
    Prose { text: String },
    Code { code: String, language: String, line_numbers: bool },
    ToolCall { name: String, args: String, collapsed: bool },
    ToolResult { output: String, success: bool, truncated: bool },
    AgentThought { text: String },
    Error { text: String },
    Warning { text: String },
    Divider,
}
```

**Block detection algorithm:**
1. Accumulate content_chunk events into `streaming_buffer`
2. On content_complete, scan buffer for markdown code fences (```)
3. If code fence detected: split into Prose/Code blocks
4. If JSON detected in tool_call data: format as key-value
5. If error event: create Error block with red styling
6. If thinking event: dim/italic styling, collapsible
7. Add Divider between agent responses

**Rendering with Ratatui:**
- Prose: `Paragraph::new(text).wrap(Wrap { trim: false })`
- Code: styled `Paragraph` with background color
- ToolCall: bordered `Block` with title "tool: name"
- ToolResult: indented under ToolCall, truncated to 20 lines with expand indicator
- AgentThought: dim foreground, italic
- Error: red foreground, bordered `Block`
- Scroll: `Scrollbar` widget with position indicator

**Error handling:**
- Buffer overflow (>10,000 blocks): drop oldest 20%
- Extremely long lines (>2000 chars): word-wrap at pane width
- Non-UTF8 content: replace invalid sequences with U+FFFD
- Empty response: show nothing (no placeholder needed)

#### 5. `tui/input_bar.rs` — Input Bar (~120 lines)

**Responsibilities:**
- Bottom-aligned single-line text input
- Readline-style keybindings (Ctrl+A/E for home/end)
- Input history (last 100 commands, persist to ~/.config/nexus/history)
- Display input prompt with mode indicator
- Show placeholder text when empty

**Data structures:**
```rust
struct InputBar {
    buffer: String,           // Current input text
    cursor_pos: usize,        // Cursor position in buffer
    history: Vec<String>,     // Input history (max 100)
    history_pos: Option<usize>, // Current history navigation position
    mode: InputMode,           // Chat | Command | Shell
}

enum InputMode {
    Chat,       // Default: free-form text
    Command,    // / prefix: slash-command execution
    Shell,      // ! prefix: shell passthrough
}
```

**Keybindings:**
- `Char(c)` → insert character at cursor
- `Enter` → submit input, add to history
- `Backspace` → delete character before cursor
- `Delete` → delete character at cursor
- `Left/Right` → move cursor
- `Up/Down` → history scroll
- `Home/Ctrl+A` → move to start
- `End/Ctrl+E` → move to end
- `Ctrl+W` → delete word before cursor
- `Ctrl+U` → clear entire buffer
- `Tab` → autocomplete (Phase 1b: file paths, Phase 2+: commands/agents/models)

**Edge cases:**
- Empty input on Enter: ignore
- Input longer than pane width: scroll horizontally, show overflow indicator
- Duplicate history entry: move to top (don't duplicate)
- History file read failure: start with empty history

#### 6. `tui/status_bar.rs` — Status Bar (~80 lines)

**Responsibilities:**
- Single-line bar at bottom of screen (above input bar)
- Left-aligned: model name, provider, effort level
- Right-aligned: token usage, session time, agent state
- Color-coded: green = ready, yellow = thinking, red = error

**Data:**
```rust
struct StatusBar {
    model_name: String,
    provider: String,
    effort_level: String,
    agent_state: String,         // idle | thinking | working | error
    token_count: (u64, u64),     // (in, out)
    session_time: Duration,
    backend_alive: bool,
}

fn render_status_bar(area: Rect, buf: &mut Buffer, status: &StatusBar)
    // Left: "[◈ llama3-8b | local | medium]"
    // Right: "[▶ thinking | 12.4k in / 3.2k out | 2m 14s]"
```

**Color coding:**
- Backend alive + idle: green foreground
- Backend alive + thinking: yellow foreground with spinner
- Backend alive + error: red foreground
- Backend dead: dim red with "DEAD" indicator
- Token counts: dim white

#### 7. `tui/task_inspector.rs` — Task Inspector Panel (~180 lines)

**Responsibilities:**
- Toggle on/off with Ctrl+T
- Shows live state of the current task
- Multiple panels: Overview, Trace, Context
- Per-task status tree (if multi-agent)
- Plan step progression with checkmarks

**Data structures:**
```rust
struct TaskInspector {
    visible: bool,
    active_tab: InspectorTab,  // Overview | Trace | Context | Memory
    task: Option<TaskState>,
}

struct TaskState {
    status: String,
    agent: String,
    plan_steps: Vec<PlanStep>,
    current_tool: Option<String>,
    iterations: u32,
    messages: u32,
    token_count: (u64, u64),
    context_fill: f64,  // 0.0 - 1.0
}
```

**Panels:**
- Overview: Task tree with checkmark/loading/spinner per step
- Trace: Chronological log of events with timestamps
- Context: Visual bar showing context window fill percentage

**Updating:**
- On ACP event received: extract state info and update TaskState
- Thinking events → update status to "thinking", increment iterations
- Tool call → update current_tool
- Content chunks → increment token count estimate
- State change → update status string

#### 8. `tui/resource_monitor.rs` — Resource Monitor (~100 lines)

**Responsibilities:**
- Show CPU utilization (per-core bar chart if available)
- RAM usage (current / available)
- VRAM usage per GPU (if NVIDIA/CUDA)
- Toggle on/off via keybind

**Data:**
```rust
struct ResourceMonitor {
    visible: bool,
    cpu_percent: f64,
    ram_used: u64,
    ram_total: u64,
    vram_used: Option<u64>,
    vram_total: Option<u64>,
    gpu_util: Option<f64>,
}
```

**Implementation notes:**
- Phase 1b: simple polling with `sys-info` crate or similar
- Phase 2+: integrate with Python backend's `/runtime status` for GPU data
- Refresh rate: 500ms (background tokio task)

#### 9. `tui/theme.rs` — Theme System (~100 lines)

**Responsibilities:**
- Load themes from `~/.config/nexus/themes/*.toml`
- 2 built-in themes: `dark` and `light`
- Apply theme colors to all Ratatui styles
- Hot-reload on SIGHUP or every 30s

**Data structures:**
```rust
#[derive(Deserialize)]
struct Theme {
    name: String,
    colors: ThemeColors,
    icons: ThemeIcons,
    borders: BorderStyle,
}

#[derive(Deserialize)]
struct ThemeColors {
    background: String,    // Hex: "#1a1b26"
    foreground: String,
    accent: String,        // Primary accent
    success: String,
    warning: String,
    error: String,
    muted: String,
    surface: String,       // Panel backgrounds
}
```

**Mapping to Ratatui:**
```rust
impl Theme {
    fn to_ratatui_style(&self, color_key: &str) -> Style {
        // Parse hex string to Color::Rgb
        // Return Style::default().fg(parsed_color).bg(theme.background)
    }
}
```

#### 10. `app.rs` — App State Machine (~150 lines)

**Responsibilities:**
- Central state for all TUI components
- Message-passing model (inspired by Bubbletea's Elm architecture)
- Handle state transitions based on ACP events and keyboard input

**Data:**
```rust
struct App {
    // TUI components
    chat: ChatPane,
    input: InputBar,
    status: StatusBar,
    inspector: TaskInspector,
    resource_monitor: ResourceMonitor,
    layout: LayoutState,
    
    // App state
    state: AppState,         // Running | WaitingForPrompt | Interrupted | Exiting
    mode: InputMode,
    backend_alive: bool,
    
    // Config
    config: Config,
    theme: Theme,
}

enum AppState {
    Running,               // Normal operation
    WaitingForPrompt,      // Agent is processing
    Interrupted,           // Ctrl+C pressed, showing dialog
    ConfirmQuit,           // /quit pressed, showing confirmation
    Error(String),         // Fatal error displayed
    Exiting,               // Shutdown in progress
}
```

**Update method:**
```rust
impl App {
    fn update(&mut self, event: AppEvent) -> Vec<Command> {
        // Returns Commands to execute (send ACP message, toggle pane, etc.)
        // Inspired by Bubbletea's model -> (Model, Cmd) pattern
        match event {
            AppEvent::AcpNotification { method, params } => self.handle_acp_event(method, params),
            AppEvent::KeyPressed(key) => self.handle_key(key),
            AppEvent::Tick => self.tick(),
        }
    }
}
```

#### 11. `config/loader.rs` — Config Loader (~80 lines)

**Responsibilities:**
- Load TOML config from `~/.config/nexus/config.toml`
- Apply CLI arg overrides on top
- Provide default values for all fields
- Validate config on load

**File location priority:**
1. `$NEXUS_CONFIG` env var
2. `./.nexus/config.toml` (project-local)
3. `~/.config/nexus/config.toml` (user global)
4. Default values

#### 12. `config/types.rs` — Config Types (~40 lines)

```rust
#[derive(Deserialize)]
struct Config {
    model: Option<String>,
    provider: Option<String>,
    workspace: Option<String>,
    theme: String,              // Default: "dark"
    layout: LayoutPreset,       // Default: "minimal"
    keybindings: Option<Vec<Keybinding>>,
}

#[derive(Deserialize)]
struct Keybinding {
    action: String,
    key: String,      // "ctrl-p", "page-up", etc.
}
```

### Dependencies Update

```toml
[dependencies]
# Existing (Phase 1a)
clap = { version = "4", features = ["derive"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
thiserror = "2"

# NEW — TUI
ratatui = "0.29"
crossterm = "0.28"

# NEW — Config
toml = "0.8"
directories = "6"

# NEW — Utilities
uuid = { version = "1", features = ["v4"] }
chrono = "0.4"
```

### Verification Criteria

1. `cargo build` succeeds (0 errors, 0 warnings)
2. `nexus chat` opens Ratatui TUI with layout + status bar + input bar
3. Typing text and pressing Enter sends ACP prompt, response appears in chat pane
4. Ctrl+T toggles task inspector, Ctrl+P opens command palette
5. Ctrl+C shows interrupt dialog with "Cancel/continue/redirect"
6. Window resize triggers layout recomputation
7. All 916+ Python tests still pass
8. Input history persists between sessions

---

## Phase 2 — Memory & Agent Depth

**Goal:** Full memory system (all 5 tiers), multi-agent execution, agent council, boomerang tasks, memory browser TUI.

**Estimated effort:** ~2,000 lines, ~2-3 weeks

### Memory Browser TUI

**File:** `tui/memory_browser.rs`

**Features:**
- Toggle with keybind (Ctrl+M)
- Shows all memory tiers in explorable tree
- Each entry shows: content (truncated), tier, type, timestamps, access frequency, relevance score
- Search/filter by tier, category, date range
- Manual add/edit/delete of memory entries

### Memory Retention Scoring

**File:** `memory/memory_manager.py` (modify)

**Features:**
- Implement MemoryOS heat score: `score = N_visit * w1 + interaction * w2 + recency * w3`
- Periodic compaction: every 50 messages, score all entries, prune lowest-scored 20%
- Configurable thresholds for auto-promote (STM → MTM → LTM)

### Boomerang Tasks

**File:** `tools/agent_tools.py` (NEW)

**Features:**
- `spawn_agent(tool: str, params: dict) -> str` — create sub-agent with specific tool
- `ask_agent(prompt: str, agent_type: str) -> str` — query another agent
- `delegate_task(task: str, specialist: str) -> str` — delegate full task to specialist
- Structured output: sub-agent returns JSON with `{result, summary, confidence}`

### Agent Council

**File:** `core/debate.py` (enhance existing)

**Features:**
- Council convenes 3-5 agents with different personas
- Each evaluates independently, votes on approach
- Disagreements surfaced as explicit decision points for user
- Structured output: `{vote: yes/no/maybe, reasoning, confidence}`

### Verification Criteria

1. Memory browser opens and shows entries from all tiers
2. Memory retention scores are computed on search/compact
3. Boomerang tasks complete and return structured results
4. Agent council renders decision with vote breakdown

---

## Phase 3 — Runtime & Model Depth

**Goal:** Full runtime registry (10 runtimes), model benchmarking, capability detection, provider failover.

**Estimated effort:** ~1,500 lines, ~2 weeks

### Full Runtime Registry

**File:** `llm/runtime_manager.py` (enhance existing)

**Add runtimes:**
- llama.cpp (already supported)
- Ollama (already supported)
- vLLM (new: spawn subprocess, probe API)
- SGLang (new: spawn subprocess, probe API)
- MLX (new: detect macOS, check Python package)
- LM Studio (new: probe localhost:1234)
- ExLlamaV2 (new: spawn TabbyAPI subprocess)
- KoboldCpp (new: probe localhost:5001)
- TensorRT-LLM (new: check Docker/image presence)
- ONNX Runtime (already partial)

### Model Benchmarking

**File:** `cli/commands/model_mixin.py` (enhance)

**Commands:** `/model benchmark [id] [--compare id2]`

**Metrics:**
- Time to first token (TTFT)
- Tokens per second (throughput)
- Peak VRAM usage
- Context fill speed
- Quality score (perplexity on standard prompt)

### Capability Detection

**File:** `llm/model_manager.py` (enhance)

**Auto-probe:**
- Max context length (binary search fill test)
- Function calling support (structured output test)
- System prompt adherence test
- Code generation quality test
- Streaming support

### Provider Failover

**File:** `llm/providers/factory.py` (enhance existing FallbackProvider)

**Features:**
- Wire SmartRouter to agent loop
- Rate limit header tracking
- Cost-based routing (cheapest eligible provider)
- Latency-based routing (fastest in last 5 calls)

### Cost Tracking Dashboard

**File:** `tui/cost_panel.rs` (NEW)

**Features:**
- Per-provider running cost with projections
- Per-session cost breakdown
- Per-model cost comparison
- Export to CSV/JSON

---

## Phase 4 — TUI Excellence

**Goal:** Full theme system (8 themes), 6 layout presets, command palette, notification toasts, keyboard-first accessibility.

**Estimated effort:** ~1,200 lines, ~2 weeks

### 8 Built-in Themes

**File:** `tui/themes/` (directory with TOML files)

- `dark.toml` — Default dark terminal theme
- `light.toml` — Inverted for light terminals
- `catppuccin-mocha.toml` — Catppuccin color scheme
- `tokyo-night.toml` — Tokyo Night palette
- `gruvbox.toml` — Gruvbox palette
- `nord.toml` — Nord palette
- `high-contrast.toml` — Accessibility high-contrast
- `minimal.toml` — Near-monochrome, zero visual noise

### 6 Layout Presets

**File:** `tui/layout.rs` (enhance)

- `minimal` — Single full-width chat pane + status bar
- `developer` — Chat + file diff side-by-side
- `researcher` — Chat + memory browser + web results
- `orchestrator` — Chat + agent graph + task inspector
- `monitor` — Chat + resource monitor + analytics
- `custom` — User-defined layout saved to config

### Command Palette

**File:** `tui/command_palette.rs` (NEW)

**Features:**
- Ctrl+P to open
- Fuzzy-searchable: commands, agents, models, skills
- Results sorted by relevance
- Enter to execute, Esc to dismiss
- History of recently used commands

### Notification Toasts

**File:** `tui/notifications.rs` (NEW)

**Features:**
- Slide in from top-right
- Auto-dismiss after 3 seconds
- Types: info, success, warning, error
- Queue system: max 5 visible, older ones dismissed
- Colors match theme

### Accessibility Pass

- Ensure all keyboard actions have visible indicators
- Add screen reader hints via terminal bell on errors
- High-contrast theme meets WCAG AA (4.5:1 contrast ratio)
- Input bar shows mode indicator even when empty

---

## Phase 5 — Platform Depth

**Goal:** Plugin system, skills, git integration, full MCP, installation ceremony, self-update, doctor.

**Estimated effort:** ~1,500 lines, ~2 weeks

### Plugin System

**File:** `core/plugins.py` (enhance existing)

**Features:**
- Plugin signatures verified against public key registry
- Sandboxed plugin execution
- Plugin capabilities declared and audited at install
- Plugin marketplace discovery (future)

### Skills System

**File:** `skills/` (enhance existing)

**Features:**
- Skill versioning (semver in frontmatter)
- Skill publishing (export as shareable markdown)
- Skill import from URL
- Skill dependency resolution

### Git Integration

**Features:** (enhance existing git_ops.py and session/checkpoint.py)

- `git branch` from within REPL
- `git commit --agent` with auto-generated message
- `git pr create` with branch-based diff
- `git checkpoint` before destructive operations
- `git rollback` to restore from checkpoint

### Full MCP Ecosystem

**Features:** (enhance existing mcp/)

- MCP over HTTP SSE (not just stdio)
- MCP server health monitoring with auto-restart
- Per-MCP-server approval policy configuration
- MCP tool discovery: `/tools mcp list/explore`

### Installation Ceremony

**Files:** `install.sh`, `install.ps1`, Cargo.toml (release profile)

**Features:**
- One-line curl-sh installer for Linux/macOS
- PowerShell installer for Windows
- SHA256 checksum verification
- PATH addition with backup
- `nexus doctor` post-install verification

### Self-Update

**File:** `core/updater.py` (enhance existing for hybrid)

**Features:**
- Check GitHub releases for new Rust binary
- Check PyPI for new Python package
- Atomic binary replacement
- Rollback to previous version

### doctor Command Enhancement

**File:** `nexus-rs/src/main.rs` (enhance existing doctor)

**Extended checks:**
- Rust binary integrity and version
- Python 3.10+ availability
- `nexus-agent` package installed
- ACP backend can start (--dry-run)
- Config file validity
- Model availability
- Runtime detection
- Provider connectivity
- Memory system health
- Performance smoke test (startup time measurement)

---

## Phase 6 — Polish & Competitive Edge

**Goal:** Performance contracts in CI, competitive benchmarking automation, continuous improvement.

**Estimated effort:** ~800 lines, ~1 week

### Performance Contracts

**File:** `.github/workflows/benchmark.yml` (NEW)

```yaml
name: Performance Benchmarks
on: [push, pull_request]
jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo build --release
      - run: cargo bench
      - name: Check contracts
        run: |
          assert "Cold startup < 150ms"
          assert "Warm startup < 50ms"
          assert "TTFT (local 8B Q4) < 500ms"
          assert "Memory search (100K) < 10ms"
          assert "Config load < 5ms"
```

**Contracts to enforce:**
| Metric | Contract | Violation Action |
|--------|----------|------------------|
| Cold startup | < 150ms | Block PR from merge |
| Warm startup | < 50ms | Block PR from merge |
| First token (local, 8B, Q4) | < 500ms | Warning |
| Memory semantic search (100K) | < 10ms p99 | Block PR from merge |
| Tool dispatch overhead | < 1ms | Warning |
| Config load | < 5ms | Warning |
| TUI frame rate | ≥ 60 fps | Warning |

### Competitive Benchmarking

**Script:** `scripts/benchmark-compare.sh` (NEW)

**Metrics:**
- Cold start time vs Claude Code, OpenCode, Aider
- Time to first response on standard task
- Command tree depth
- Supported runtimes count
- Supported providers count
- Memory persistence quality
- Multi-agent capability
- Installation complexity (1-10)
- TUI visual quality (1-10)

**Monthly cadence:** GitHub Actions cron job runs comparison, files gap report.

### Documentation Pass

**Files to create/update:**
- Architecture Decision Records (ADRs) for: Rust hybrid, memory tiers, ACP protocol, Ratatui choice
- API documentation for all public Rust interfaces
- User guide with examples for every feature
- Troubleshooting guide for common failure modes
- Migrating from Python CLI guide

---

## Dependency Map

```
Phase 1a (✅) ───────────────► Phase 1b (🔜) ──────────────► Phase 1c
     │                              │                              │
     │                              │                              │
     ▼                              ▼                              ▼
Phase 2 ◄──────────────────── Phase 3 ◄──────────────────── Phase 4
     │                              │                              │
     │                              │                              │
     ▼                              ▼                              ▼
Phase 5 ◄──────────────────── Phase 6
```

**Dependencies:**
- Phase 1b requires Phase 1a (complete)
- Phase 1c requires Phase 1b (Ratatui TUI must be stable first)
- Phase 2 requires Phase 1b (TUI for memory browser, agent inspector)
- Phase 3 requires Phase 2 (model benchmarking needs memory for persistence)
- Phase 4 requires Phase 1b (TUI foundation needed for theme/layout)
- Phase 5 requires Phase 3 (installation needs runtime registry)
- Phase 6 requires everything else (benchmarks need stable base)

---

## File Count & Lines Estimate

| Phase | New Rust Files | Modified Rust | New Python | Modified Python | Total Lines |
|-------|---------------|---------------|------------|-----------------|-------------|
| 1a (done) | 5 | 0 | 1 | 1 | ~650 Rust + ~200 Python |
| 1b | 12 | 2 | 0 | 0 | ~1,500 Rust |
| 2 | 1 | 2 | 1 | 3 | ~200 Rust + ~500 Python |
| 3 | 1 | 0 | 0 | 4 | ~100 Rust + ~800 Python |
| 4 | 3 | 2 | 0 | 0 | ~600 Rust |
| 5 | 2 | 1 | 0 | 3 | ~300 Rust + ~600 Python |
| 6 | 1 | 1 | 0 | 0 | ~400 Rust + ~300 Scripts |
| **Total** | **24** | **8** | **2** | **11** | **~3,750 Rust + ~2,400 Python** |
