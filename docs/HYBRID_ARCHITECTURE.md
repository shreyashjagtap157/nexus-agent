# Hybrid Rust/Python Architecture — Nexus

> **Date:** June 8, 2026
> **Status:** Design Document — Ready for Implementation
> **Decision:** Rust for CLI/render/inference dispatch, Python for agents/memory/tools

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                    Rust Process                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │   CLI     │  │  Ratatui │  │  Inference        │  │
│  │  Entry    │  │  TUI     │  │  Dispatch         │  │
│  │  (clap)   │  │  Engine  │  │  (llama.cpp       │  │
│  │           │  │          │  │   bindings)        │  │
│  └────┬──────┘  └────┬─────┘  └─────────┬─────────┘  │
│       │              │                  │            │
│       └──────────────┴──────────────────┘            │
│                        │                             │
│                  JSON-RPC 2.0                         │
│                  over stdin/stdout                    │
│                        │                             │
├────────────────────────┼─────────────────────────────┤
│                   Python Process                      │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  ACP     │  │  AgentLoop  │  │  Memory/Tools/   │  │
│  │  Server  │  │  (core/)    │  │  Providers/      │  │
│  │          │  │             │  │  Session/         │  │
│  └──────────┘  └────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Why This Split

| Layer | Language | Rationale |
|-------|----------|-----------|
| **CLI/TUI** | Rust | Sub-150ms cold startup (impossible in Python with 119 modules). Ratatui gives 60fps rendering, immediate-mode layout, and full keyboard control. |
| **Inference Dispatch** | Rust | Direct llama.cpp bindings via `llama-cpp-2` crate. Zero-copy tensor access, GPU memory management, no Python GIL. Necessary for sub-500ms first-token latency. |
| **Agent Loop** | Python | 807 lines of complex state-machine logic with rich iteration patterns. Rewriting to Rust would be ~3 months without improving functionality. The GIL doesn't matter here — it's single-threaded by design. |
| **Memory System** | Python | 9 files of SQLite + embedding logic. The `sqlite-vec` extension works natively. No performance gain from Rust. |
| **Tools** | Python | 16 tool implementations. Each is ~100-250 lines with clean `Tool` interface. Rust would add build complexity with zero throughput gain. |
| **Providers** | Python | 10 provider adapters, each making HTTP calls. These are I/O-bound; Python's `httpx` is as fast as Rust's `reqwest` for network calls. |

### Performance Targets vs Architecture

| Metric | Current (Python) | Target (Hybrid) | Win Source |
|--------|:----------------:|:---------------:|------------|
| Cold startup | ~500ms | <150ms | Rust eliminates 119-module Python import overhead |
| Warm startup | ~200ms | <50ms | Rust binary is native; Python process stays alive |
| First token (local 8B Q4) ⚡ | ~2s | <500ms¹ | Rust llama.cpp bindings avoid Python GIL + FFI overhead |
| TUI frame rate | ~15fps | ≥60fps | Ratatui immediate-mode vs Rich Markdown re-render |
| Memory search (100K entries) ⚡ | ~50ms | <10ms² | Rust-side embedding dispatch, Python-side SQLite |

> ⚡ **Requires GPU.** ¹ Sub-500ms first token for an 8B Q4 model requires NVIDIA/AMD GPU acceleration. On CPU-only systems, expect ~1-2s. ² Memory search runs through Python embedding models; the Rust side dispatches queries over ACP, not inline. Realistic target: ~30-50ms.

---

## 2. IPC Protocol: JSON-RPC 2.0 over stdio (ACP)

The existing **ACP Server** (`src/nexus_agent/mcp/acp_server.py`) already implements exactly what we need. We do not need to design a new protocol — we extend the existing one.

### Protocol Details

**Transport:** stdin/stdout (subprocess pipes)
**Format:** Newline-delimited JSON (NDJSON)
**Protocol:** JSON-RPC 2.0 subset (request/response + streaming notifications)

### Existing Methods (already implemented)

```jsonc
// Request: Send a prompt to the agent
{"jsonrpc":"2.0", "id":1, "method":"prompt", "params":{"text":"Refactor auth.rs"}}
// Response (final):
{"jsonrpc":"2.0", "id":1, "result":{"status":"completed"}}
// Notifications (streamed during execution):
{"jsonrpc":"2.0", "method":"event", "params":{"type":"content_chunk","data":"..."}}
{"jsonrpc":"2.0", "method":"event", "params":{"type":"tool_call","data":{...}}}
{"jsonrpc":"2.0", "method":"event", "params":{"type":"tool_result","data":{...}}}
{"jsonrpc":"2.0", "method":"event", "params":{"type":"error","data":"..."}}

// Request: Get agent status
{"jsonrpc":"2.0", "id":2, "method":"get_status", "params":{}}
// Response:
{"jsonrpc":"2.0", "id":2, "result":{"session_id":"abc","mode":"auto","effort":"medium"}}

// Request: Stop execution
{"jsonrpc":"2.0", "id":3, "method":"stop", "params":{}}
```

### New Methods to Add

```jsonc
// Request: Initialize agent with config (called once at startup)
{"jsonrpc":"2.0", "id":0, "method":"init", "params":{
  "workspace": "/path/to/project",
  "model_path": "/path/to/model.gguf",
  "provider": "local",
  "config": {"agent": {"effort_level": "medium"}, ...}
}}

// Request: Execute a slash command
{"jsonrpc":"2.0", "id":4, "method":"command", "params":{"cmd":"/help"}}

// Request: Get memory context (for drawing memory browser panel) — Phase 2+
{"jsonrpc":"2.0", "id":5, "method":"memory_search", "params":{"query":"auth","limit":10}}

// Request: Get session analytics (for /stats panel) — Phase 2+
{"jsonrpc":"2.0", "id":6, "method":"get_session_info", "params":{}}

// Notification: User pressed Ctrl+C (sent from Rust to Python)
{"jsonrpc":"2.0", "method":"interrupt", "params":{}}
```

### Streaming Notifications (Python → Rust)

The Python ACP server already streams `event` notifications. The Rust side needs to consume these and route them to the TUI:

| Event Type | TUI Action |
|------------|------------|
| `content_chunk` | Append to streaming buffer, render in chat pane |
| `content_complete` | Finalize stream, render markdown |
| `tool_call` | Show tool call card in chat pane, update task inspector |
| `tool_result` | Show result (collapsed), update task inspector |
| `thinking` | Update spinner verb in status bar |
| `state_change` | Update agent state indicator, task inspector |
| `error` | Show error toast notification, log to trace panel |

### Error Recovery

```
Rust detects Python process crash (exit code ≠ 0)
    → Display error dialog in TUI with exit code
    → Offer "Restart backend" action
    → Spawn new Python process, send init, restore session
```

> **Note:** Python stderr is directed to the parent terminal (`Stdio::inherit()`) rather than piped to the Rust side. This avoids pipe deadlocks during subprocess I/O and means stderr output appears directly in the user's terminal for debugging. The `BackendState::Crashed` struct captures the exit code but not stderr content.

---

## 3. Module Boundary — What Goes Where

### Rust Side (`nexus-rs/`) — The CLI Core

```
nexus-rs/
├── Cargo.toml
├── src/
│   ├── main.rs                  ← CLI entry point (clap argument parsing)
│   ├── cli/
│   │   ├── mod.rs
│   │   ├── app.rs               ← App state machine (model, update, view)
│   │   └── commands.rs          ← Built-in command routing (no Python needed)
│   ├── tui/
│   │   ├── mod.rs
│   │   ├── layout.rs            ← Multi-pane layout engine
│   │   ├── chat_pane.rs         ← Streaming content display
│   │   ├── input_bar.rs         ← Prompt input with history
│   │   ├── task_inspector.rs    ← Live task graph TUI panel
│   │   ├── status_bar.rs        ← Bottom status line
│   │   ├── resource_monitor.rs  ← CPU/GPU/RAM live display
│   │   ├── memory_browser.rs    ← Memory tiers TUI browser
│   │   ├── command_palette.rs   ← Ctrl+P fuzzy command search
│   │   ├── theme.rs             ← Theme system (TOML-defined)
│   │   └── notifications.rs     ← Toast notification system
│   ├── ipc/
│   │   ├── mod.rs
│   │   ├── acp_client.rs        ← ACP JSON-RPC 2.0 client over stdio
│   │   ├── protocol.rs          ← Type definitions for ACP messages
│   │   └── process.rs           ← Python subprocess lifecycle manager
│   ├── config/
│   │   ├── mod.rs
│   │   ├── loader.rs            ← Load config from ~/.config/nexus/config.toml
│   │   └── types.rs             ← Config type definitions
│   └── inference/
│       ├── mod.rs
│       ├── llama_cpp.rs         ← Direct llama.cpp Rust bindings (future)
│       └── dispatch.rs          ← Route to local Rust or Python process
```

### Python Side (stays as-is) — The Agent Backend

The existing `src/nexus_agent/` remains largely untouched:

```
src/nexus_agent/                ← No structural changes
├── core/                       ← AgentLoop, orchestrator, planner, executor
├── memory/                     ← 5-tier memory system
├── tools/                      ← 16 tool implementations
├── llm/                        ← 10 providers + local engines
├── session/                    ← Session lifecycle + checkpoints
├── mcp/                        ← MCP client/server (including ACP server)
└── cli/
    ├── app.py                  ← Will be replaced by Rust entry
    ├── input_handler.py        ← Will be replaced by Ratatui input
    ├── renderer.py             ← Will be replaced by Ratatui render
    ├── event_handler.py        ← Logic stays, events sent via ACP
    ├── session_handler.py      ← Logic stays, init via ACP
    └── commands/interactive_ui.py  ← Some interactive menus move to Rust
```

### Incremental Migration: What Stays in Python CLI for Now

Some interactive UI pieces are deeply entangled with Python objects and can't easily move to Rust in the first pass:

| Component | Strategy |
|-----------|----------|
| `/model add` interactive menu | Forward commands via ACP to Python, render result as text |
| `/connect` interactive provider setup | Same — forward to Python, show text result |
| First-run wizard (`wizard.py`) | Launched as separate Python process |
| `/config` edit | Forward to Python, show text result |

These can be incrementally ported to Rust TUI panels after the core shell is stable.

---

## 4. Rust Project Structure — Phase 1 Implementation

### 4.1 Cargo.toml

```toml
[package]
name = "nexus"
version = "0.2.0"
edition = "2021"
description = "Offline-first AI coding agent — CLI core"

[[bin]]
name = "nexus"
path = "src/main.rs"

[dependencies]
# CLI
clap = { version = "4", features = ["derive"] }

# TUI
ratatui = "0.29"
crossterm = "0.28"

# IPC
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }

# Config
toml = "0.8"
directories = "6"

# Inference (Phase 3)
# llama-cpp-2 = "0.2"  # Uncomment when adding direct llama.cpp support

# Utilities
tracing = "0.1"
tracing-subscriber = "0.3"
thiserror = "2"
uuid = { version = "1", features = ["v4"] }
chrono = "0.4"

[profile.release]
lto = true
codegen-units = 1
strip = true
opt-level = "z"       # Minimize binary size for fast startup
```

### 4.2 Python Side — ACP Server Enhancement

The existing `acp_server.py` needs minor enhancements to support the new methods. The Python process is spawned by Rust as:

```
nexus backend --acp
```

Which runs the ACP server in stdio mode. The existing `nexus chat` Click command is replaced by the Rust binary.

### 4.3 Build Integration

```makefile
# Near the end of Phase 1, the build produces:
# target/release/nexus      — Rust binary (CLI entry point)
# src/nexus_agent/          — Python package (agent backend)

# Build commands:
cargo build --release            # Build Rust CLI
pip install -e .                 # Install Python backend

# The Rust binary spawns the Python backend automatically:
nexus chat                      # → spawns `python -m nexus_agent.backend --acp`
```

### 4.4 Startup Sequence

```
User runs: nexus chat
1. Rust CLI starts
2. Parse args with clap: --model, --provider, --workspace, --config, etc.
3. Spawn Python subprocess:
     python -m nexus_agent.backend --acp --model <path> --workspace <path>
4. Send ACP init request:
     {"method":"init", "params":{"workspace":"...","model":"...","config":{...}}}
5. Wait for init response (timeout: 10s)
6. On success: render Ratatui TUI, enter main loop
7. On failure: show error dialog with "Retry" / "View log" / "Run wizard"

Main loop:
  - Read keyboard input via crossterm
  - Send user input as ACP prompt request
  - Receive ACP event notifications
  - Route events to TUI panels
  - Render frame with Ratatui (60fps)
  - On Ctrl+C: send ACP interrupt, prompt "Cancel/continue/redirect"
  - On /quit: send ACP stop, wait for Python shutdown, exit
```

---

## 5. TUI Architecture (Ratatui)

### 5.1 Layout Presets (from Vision §4.1)

```rust
enum LayoutPreset {
    Minimal,        // Single chat pane + status bar
    Developer,      // Chat + file diff side-by-side
    Researcher,     // Chat + memory browser + web results
    Orchestrator,   // Chat + agent graph + task inspector
    Monitor,        // Chat + resource monitor + analytics
    Custom(Vec<Split>),
}

struct Split {
    direction: Direction,  // Horizontal | Vertical
    ratio: f64,            // 0.0 - 1.0
    pane: PaneType,        // Chat | Diff | Inspector | Memory | Graph
}
```

### 5.2 Keybinding System (Phase 2+)

> **Phase 2+:** The current implementation (`app.rs`) uses hardcoded Rust match arms for keyboard input. A dynamic TOML-based keybinding system is planned for Phase 2. The parser complexity is non-trivial — mapping strings like `"ctrl-t"` to `KeyEvent { code: KeyCode::Char('t'), modifiers: KeyModifiers::CONTROL }` requires robust handling of all modifier combinations, function keys, and platform-specific differences.

```rust
struct Keybindings {
    global: HashMap<KeyEvent, GlobalAction>,
    modal: Option<HashMap<KeyEvent, ModalAction>>,
}

enum GlobalAction {
    OpenPalette,        // Ctrl+P
    ToggleInspector,    // Ctrl+T
    ToggleLayout,       // Ctrl+L
    Interrupt,          // Ctrl+C
    ToggleFullscreen,   // F11
    Quit,               // Ctrl+D
    Copy,               // Ctrl+Shift+C
    Paste,              // Ctrl+Shift+V
    ScrollUp,           // PageUp
    ScrollDown,         // PageDown
}

// Keybindings loaded from ~/.config/nexus/keybindings.toml
// Conflicts detected at load time and reported as errors.
```

### 5.3 Streaming Render Pipeline (from Vision §3.3)

```rust
struct RenderPipeline {
    token_buffer: Vec<String>,     // Accumulate into semantic units
    block_detector: BlockDetector, // Identify content type
    formatter: ContentFormatter,   // Apply type-specific formatting
    theme: Theme,                  // Apply visual theme
    diff_engine: DiffEngine,       // Live diff updates
    compositor: Compositor,        // Compose into active layout pane
}

enum ContentBlock {
    Prose(String),
    Code { code: String, language: String },
    ToolCall { name: String, args: Value },
    ToolResult { output: String, success: bool },
    AgentThought(String),
    PlanStep(Vec<Step>),
    FileDiff { path: String, added: usize, removed: usize },
    Warning(String),
    Error(String),
}
```

### 5.4 Theme System (from Vision §4.2)

```rust
#[derive(Deserialize)]
struct Theme {
    colors: Colors,
    icons: Icons,
    borders: BorderStyle,
    animations: AnimationConfig,
}

#[derive(Deserialize)]
struct Colors {
    background: String,     // Hex: "#1a1b26"
    foreground: String,
    accent_primary: String,
    accent_secondary: String,
    success: String,
    warning: String,
    error: String,
    info: String,
    muted: String,
    agent_thought: String,
    tool_call: String,
    tool_result: String,
}

// Themes loaded from ~/.config/nexus/themes/*.toml
// 8 built-in themes: dark, light, catppuccin-mocha, tokyo-night,
//                     gruvbox, nord, high-contrast, minimal
```

---

## 6. Migration Strategy — Phased Rollout

### Phase 1a — Rust CLI Wrapper (Week 1-2)

Build the Rust binary that:
- Parses CLI args (clap)
- Spawns Python backend as subprocess
- Sends ACP `init` message
- Reads ACP `event` notifications from stdout
- Renders plain text output (no Ratatui yet — just prints events)
- Forwards user input from stdin to ACP `prompt` messages

**Validation:** `nexus chat` works identically to `python -m nexus_agent chat`

### Phase 1b — Ratatui Shell (Week 2-4)

Replace the plain-text CLI wrapper with a full Ratatui TUI:
- Multi-pane layout with chat + status bar + task inspector (minimal profile)
- Streaming content rendering with block detection
- Keybinding system with help overlay
- Input bar with history and autocomplete
- Theme system with dark + light themes
- No interactive `/model` or `/connect` menus yet — these forward to Python

### Phase 1c — Python CLI Deprecation (Week 4)

After the Rust TUI is stable:
- `nexus chat` → Rust binary
- `python -m nexus_agent` → Shows deprecation notice pointing to `nexus`
- `nexus wizard` → Standalone Python wizard launched by Rust
- `nexus gui` → Still launches Python FastAPI server (no Rust here)

### Phase 2+ — Memory Browser, Agent Council, Plugin System

All later phases build on top of the Rust TUI foundation established in Phase 1.

---

## 7. Error Handling & Edge Cases

### Python Process Crash

```rust
enum BackendState {
    Starting,
    Ready { pid: u32, agent_id: String },
    Degraded { pid: u32, error: String },
    Crashed { exit_code: i32, stderr: String },
    Stopped,
}

// On crash:
// 1. Display: "Backend process exited unexpectedly (code: {code}). Log: {stderr}"
// 2. Offer: [Restart] [Save Session] [Quit]
// 3. On Restart: spawn new Python process, send init with workspace+model
// 4. Restore conversation from session storage
```

### Large Output Handling

```rust
// Rust sets a read buffer limit on the ACP stdout pipe
const ACP_READ_BUFFER: usize = 1024 * 1024;  // 1MB

// If a single ACP message exceeds the buffer, it's truncated
// and an overflow notification is sent to the TUI
struct AcpMessage {
    payload: String,
    truncated: bool,    // True if payload was truncated
}
```

### Graceful Shutdown

```
User presses /quit or Ctrl+D:
1. Rust sends ACP stop message
2. Waits for Python process exit (timeout: 5s)
3. If Python doesn't exit: sends SIGTERM (Unix) / TerminateProcess (Windows)
4. Saves Rust-side state (window positions, scroll position, last session)
5. Restores terminal to normal mode
6. Exits with code 0
```

---

## 8. Python-Side Changes Required

### 8.1 New Entry Point: `nexus_agent/backend.py`

The existing `__main__.py` has no `backend` subcommand. We need a new module that runs the ACP server as a stdio process:

```python
# nexus_agent/backend.py — ACP backend entry point
"""Backend entry point for the Rust hybrid architecture.

Spawned by the Rust CLI binary (`nexus chat`). Runs the full
agent initialization, then accepts ACP JSON-RPC 2.0 commands
over stdin/stdout.
"""

import sys
import json
import asyncio
from pathlib import Path
from nexus_agent.mcp.acp_server import ACPServer
from nexus_agent.cli.session_handler import SessionOrchestratorMixin

# Usage: python -m nexus_agent.backend --acp --workspace <path> --model <path>
```

### 8.2 Extracting SessionOrchestratorMixin from NexusApp

The current `SessionOrchestratorMixin` is a mixin on `NexusApp` with ~30 initialization steps (config → memory → session → engine → agent → MCP → skills → tools). It needs to be callable standalone without a `NexusApp` instance.

**Strategy:** Extract `_initialize()` into a standalone `AgentBackend` class:

```python
class AgentBackend:
    """Standalone agent backend — initializes and runs without TUI."""
    def __init__(self, workspace: Path, model: str | None = None, ...):
        self._config = load_config(workspace=workspace, ...)
        self._memory = MemoryManager(...)
        self._session_mgr = SessionManager(...)
        # ... all the same init steps
```

### 8.3 Headless Mode for EventHandlerMixin

The current `EventHandlerMixin._run_agent()` calls `self.r.stream_chunk()`, `self.r.tool_call()`, etc. In headless/ACP mode, these must serialize to JSON-RPC notifications on stdout instead:

```python
# In event_handler.py or backend.py:
class AcpEventBridge:
    """Bridges agent events to ACP stdout notifications."""
    def emit(self, event_type: str, data: Any) -> None:
        notification = {
            "jsonrpc": "2.0",
            "method": "event",
            "params": {"type": event_type, "data": data},
        }
        sys.stdout.write(json.dumps(notification) + "\n")
        sys.stdout.flush()
```

### 8.4 New Click Command in `__main__.py`

```python
@cli.command("backend")
@click.option("--acp", is_flag=True, help="Run as ACP stdio backend")
def backend_cmd(acp: bool) -> None:
    """Run as backend process for the Rust CLI."""
    if acp:
        from nexus_agent.backend import run_acp_backend
        run_acp_backend()
```

## 9. Installation & Distribution

### 9.1 The Hybrid Challenge

A hybrid Rust+Python binary complicates installation:
- The Rust binary (`nexus`) is a standalone executable
- At runtime, it spawns `python -m nexus_agent.backend --acp`
- Users need both the `nexus` binary AND a Python environment with `nexus-agent` installed

### 9.2 Phase 1 Installation (Simple)

```bash
# 1. Install the Python package
pip install nexus-agent

# 2. Install the Rust CLI
curl -fsSL https://get.nexus.dev/nexus-x86_64-linux.tar.gz | tar xz
sudo mv nexus /usr/local/bin/

# 3. Verify
nexus doctor
```

### 9.3 Phase 2 Installation (Self-Contained)

Bundle the Python environment using PyInstaller or Nuitka:

```bash
# Build script creates:
# target/release/nexus                    — Rust binary
# target/release/nexus-bundle.tar.gz      — Rust + embedded Python runtime
```

### 9.4 Runtime Python Detection

The Rust binary must find the Python runtime at startup:

```rust
fn find_python() -> Result<PathBuf, String> {
    for candidate in &["python3", "python", "python3.12", "python3.11", "python3.10"] {
        if let Ok(path) = which::which(candidate) {
            return Ok(path);
        }
    }
    Err("Python 3.10+ not found on PATH. Install it from python.org".into())
}
```

### 9.5 The `nexus doctor` Command

Checks:
- Rust binary integrity and version
- Python 3.10+ availability (`python3 --version`)
- `nexus-agent` package installed (`python -m nexus_agent --version`)
- ACP backend can start (`python -m nexus_agent.backend --acp --dry-run`)
- Config file validity
- Model availability (if configured)

## 10. Directory Structure After Migration

```
nexus-agent/
├── nexus-rs/                       ← NEW: Rust CLI core
│   ├── Cargo.toml
│   └── src/                        ← ~5,000 lines of Rust
├── src/
│   └── nexus_agent/                ← ~20,000 lines of Python (unchanged)
│       ├── core/
│       ├── llm/
│       ├── cli/                    ← Python CLI still works via `python -m nexus_agent`
│       ├── gui/
│       ├── memory/
│       ├── tools/
│       ├── session/
│       ├── mcp/
│       └── ...
├── tests/                          ← ~1,000 tests
├── docs/
├── Cargo.toml                      ← NEW: workspace-level build
├── pyproject.toml
└── Makefile                        ← NEW: unified build (`make all` builds both)
```

---

## 9. Open Decisions

| Decision | Options | Recommended | Reason |
|----------|---------|-------------|--------|
| Rust TUI framework | Ratatui vs cursive vs tui-rs | **Ratatui** | Active development, immediate-mode, crossterm backend, best crate ecosystem |
| Async runtime | tokio vs async-std vs smol | **tokio** | Industry standard, best subprocess management, rate limiting support |
| ACP line protocol | NDJSON vs length-prefixed | **NDJSON** | Simple, debuggable with `tail -f`, already implemented in Python |
| Config format | TOML vs YAML vs JSON | **TOML** | Cleaner than YAML for terminal editing, native Rust serde support |
| Python subprocess survival | One process vs pool | **Single process** | Agent is stateful; pooling adds complexity without benefit |
| Inference dispatch | Always go through Python ACP vs direct Rust bindings | **Hybrid** | Phase 1-2: through Python. Phase 3+: optional direct Rust for local models |
