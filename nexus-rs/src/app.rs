//! Application state machine — central state for the Nexus TUI.
//!
//! Inspired by Bubbletea's Elm architecture:
//! - `App` is the model (holds all state)
//! - `update()` processes events and returns state changes
//! - The TUI engine calls `update()` on each event and `draw()` on each frame
//!
//! The App owns all TUI component state (chat pane, input bar, status bar, etc.)
//! and handles ACP event routing, keyboard input, and state transitions.

use std::time::Instant;

use crate::config::types::Config;
use crate::tui::inspector::InspectorPanel;
use crate::tui::render::blocks::BlockDetector;
use crate::tui::render::themes::Theme;

// ── App State ───────────────────────────────────────────────────────

/// Top-level application state.
pub struct App {
    /// Application phase.
    pub phase: AppPhase,

    /// Backend process status.
    pub backend: BackendStatus,

    /// Active configuration.
    pub config: Config,

    /// Whether the backend supports streaming.
    pub streaming: bool,

    /// Session start time (for uptime display).
    pub session_start: Instant,

    /// Token usage counters.
    pub tokens_in: u64,
    pub tokens_out: u64,

    /// Current agent state string (from ACP events).
    pub agent_state: String,

    /// Active model name.
    pub model_name: String,

    /// Active provider name.
    pub provider_name: String,

    /// Current effort level.
    pub effort_level: String,

    /// TUI layout preset.
    pub layout: String,

    /// Currently focused pane index.
    pub focused_pane: usize,

    /// Whether the task inspector is visible.
    pub inspector_visible: bool,

    /// Whether the command palette is open.
    pub palette_open: bool,

    /// Whether to quit.
    pub should_quit: bool,

    /// Error message to display (if any).
    pub error_message: Option<String>,

    /// Pending interrupt action (Ctrl+C dialog).
    pub interrupt_action: Option<InterruptAction>,

    /// Streaming content buffer (accumulated content_chunk data).
    pub stream_buffer: String,

    /// Chat message history for display.
    pub messages: Vec<ChatMessage>,

    /// Scroll offset for the chat pane.
    pub chat_scroll: usize,

    /// Input buffer text.
    pub input_buffer: String,

    /// Cursor position in input buffer.
    pub input_cursor: usize,

    /// Input history for up/down navigation.
    pub input_history: Vec<String>,

    /// Current position in input history (None = new input).
    pub input_history_pos: Option<usize>,

    /// Active inspector tab panel.
    pub inspector_tab: InspectorPanel,

    /// Active visual theme.
    pub theme: Theme,

    /// Block detector for streaming render pipeline.
    pub block_detector: BlockDetector,

    /// Memory browser overlay state.
    pub memory_browser: crate::tui::memory_browser::MemoryBrowser,

    /// System resource snapshot for monitor pane.
    pub resources: SystemResources,

    /// Terminal size at last render.
    pub terminal_width: u16,
    pub terminal_height: u16,
}

/// System resource snapshot for the resource monitor pane.
#[derive(Debug, Clone)]
pub struct SystemResources {
    /// CPU usage as percentage (0.0–100.0).
    pub cpu_usage: f32,
    /// Total physical memory in bytes.
    pub memory_total: u64,
    /// Used physical memory in bytes.
    pub memory_used: u64,
    /// Number of CPU cores.
    pub cpu_cores: usize,
    /// Host name.
    pub host_name: String,
    /// OS name/version.
    pub os_version: String,
    /// Number of running processes.
    pub process_count: usize,
}

impl Default for SystemResources {
    fn default() -> Self {
        Self {
            cpu_usage: 0.0,
            memory_total: 0,
            memory_used: 0,
            cpu_cores: 0,
            host_name: String::new(),
            os_version: String::new(),
            process_count: 0,
        }
    }
}

/// High-level application phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppPhase {
    /// Backend is starting up.
    Starting,
    /// Backend is ready, waiting for input.
    Ready,
    /// Agent is processing a prompt.
    Processing,
    /// Ctrl+C pressed — showing interrupt dialog.
    Interrupted,
    /// Fatal error — showing error screen.
    Error,
    /// Shutting down.
    Exiting,
}

/// Backend process connectivity status.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BackendStatus {
    /// Process spawned, waiting for init response.
    Connecting,
    /// Process running and initialized.
    Connected,
    /// Process running but in degraded state.
    Degraded(String),
    /// Process exited unexpectedly.
    Disconnected,
}

/// Action to take after user interrupt.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InterruptAction {
    Cancel,
    Continue,
    Redirect,
}

/// A chat message in the display buffer.
#[derive(Debug, Clone)]
pub struct ChatMessage {
    /// Message type for display styling.
    pub kind: MessageKind,
    /// Content text.
    pub content: String,
    /// Timestamp when received.
    pub timestamp: Instant,
}

/// Display-styling category for a chat message.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MessageKind {
    UserInput,
    AssistantResponse,
    ToolCall,
    ToolResult,
    Thinking,
    Error,
    Warning,
    System,
}

/// Commands that the App can return from update()
/// to instruct the TUI engine to perform side effects.
pub enum Command {
    /// Send an ACP request to the backend.
    SendAcp(String),
    /// Quit the application.
    Quit,
    /// Toggle task inspector visibility.
    ToggleInspector,
    /// Toggle command palette.
    TogglePalette,
    /// Cycle through layout presets.
    CycleLayout,
    /// Open an interactive menu (forward to Python).
    OpenMenu(String),
    /// Interrupt the current agent execution.
    InterruptAgent,
    /// Copy text to clipboard.
    CopyToClipboard(String),
    /// Change the active theme.
    ChangeTheme(String),
    /// Toggle the memory browser overlay.
    ToggleMemoryBrowser,
    /// Request memory list from backend.
    RequestMemoryList,
    /// Request memory stats from backend.
    RequestMemoryStats,
    /// No command.
    None,
}

/// Memory list result from ACP backend.
#[derive(Debug, Clone)]
pub struct MemoryListResult {
    pub entries: Vec<serde_json::Value>,
    pub count: usize,
}

// ── Events ──────────────────────────────────────────────────────────

/// Events that the App can process.
pub enum AppEvent {
    /// TUI tick (60fps frame).
    Tick,
    /// ACP event notification from backend.
    AcpNotification {
        method: String,
        data: Option<serde_json::Value>,
    },
    /// ACP response to a request.
    AcpResponse {
        id: u64,
        result: Option<serde_json::Value>,
    },
    /// Memory list response from backend.
    MemoryList {
        result: MemoryListResult,
    },
    /// Memory stats response from backend.
    MemoryStats {
        stats: serde_json::Value,
    },
    /// Keyboard key press.
    KeyPressed(crossterm::event::KeyEvent),
    /// Terminal was resized.
    Resized { width: u16, height: u16 },
    /// Backend process state change.
    BackendEvent(BackendStatus),
    /// Error from backend.
    BackendError(String),
}

// ── Implementation ──────────────────────────────────────────────────

impl App {
    /// Create a new App with default state.
    pub fn new(config: Config) -> Self {
        let theme = crate::tui::render::themes::load_theme(&config.theme, None);
        Self {
            phase: AppPhase::Starting,
            backend: BackendStatus::Connecting,
            config,
            streaming: false,
            session_start: Instant::now(),
            tokens_in: 0,
            tokens_out: 0,
            agent_state: String::new(),
            model_name: String::new(),
            provider_name: String::new(),
            effort_level: String::new(),
            layout: "minimal".to_string(),
            focused_pane: 0,
            inspector_visible: false,
            inspector_tab: InspectorPanel::Overview,
            palette_open: false,
            should_quit: false,
            error_message: None,
            interrupt_action: None,
            stream_buffer: String::new(),
            messages: Vec::new(),
            chat_scroll: 0,
            input_buffer: String::new(),
            input_cursor: 0,
            input_history: Vec::new(),
            input_history_pos: None,
            theme,
            block_detector: BlockDetector::new(),
            memory_browser: crate::tui::memory_browser::MemoryBrowser::default(),
            resources: SystemResources::default(),
            terminal_width: 80,
            terminal_height: 24,
        }
    }

    /// Refresh system resource snapshot.
    pub fn refresh_resources(&mut self) {
        use sysinfo::System;
        static SYS: std::sync::OnceLock<std::sync::Mutex<System>> = std::sync::OnceLock::new();
        let sys = SYS.get_or_init(|| {
            std::sync::Mutex::new(System::new())
        });
        if let Ok(mut sys) = sys.lock() {
            sys.refresh_cpu_all();
            sys.refresh_memory();
            self.resources = SystemResources {
                cpu_usage: sys.global_cpu_usage(),
                memory_total: sys.total_memory(),
                memory_used: sys.used_memory(),
                cpu_cores: sys.physical_core_count().unwrap_or(0),
                host_name: System::host_name().unwrap_or_default(),
                os_version: System::long_os_version().unwrap_or_default(),
                process_count: sys.processes().len(),
            };
        }
    }

    /// Process an event and return a command for the engine to execute.
    pub fn update(&mut self, event: AppEvent) -> Command {
        match event {
            AppEvent::Tick => self.on_tick(),
            AppEvent::AcpNotification { method, data } => {
                self.on_acp_event(&method, data.as_ref());
                Command::None
            }
            AppEvent::AcpResponse { id: _, result } => {
                if let Some(r) = result {
                    if let Some(status) = r.get("status").and_then(|s| s.as_str()) {
                        if status == "ready" {
                            // Init complete
                            self.phase = AppPhase::Ready;
                            self.backend = BackendStatus::Connected;
                            if let Some(sid) = r.get("session_id").and_then(|s| s.as_str()) {
                                self.add_system_message(&format!("Session: {sid}"));
                            }
                        }
                    }
                }
                Command::None
            }
            AppEvent::KeyPressed(key) => self.on_key(key),
            AppEvent::Resized { width, height } => {
                self.terminal_width = width;
                self.terminal_height = height;
                Command::None
            }
            AppEvent::BackendEvent(status) => {
                self.backend = status;
                if self.backend == BackendStatus::Connected {
                    self.phase = AppPhase::Ready;
                }
                Command::None
            }
            AppEvent::BackendError(err) => {
                self.error_message = Some(err);
                self.phase = AppPhase::Error;
                Command::None
            }
            AppEvent::MemoryList { result } => {
                let entries: Vec<crate::tui::memory_browser::MemoryEntry> = result.entries.iter().map(|v| {
                    let content = v.get("content").and_then(|c| c.as_str()).unwrap_or("").to_string();
                    let tier_str = v.get("source").and_then(|s| s.as_str()).unwrap_or("long_term");
                    let tier = match tier_str {
                        "working" => crate::tui::memory_browser::MemoryTier::Working,
                        "episodic" => crate::tui::memory_browser::MemoryTier::Episodic,
                        "vector" => crate::tui::memory_browser::MemoryTier::VectorStore,
                        "user_profile" | "profile" => crate::tui::memory_browser::MemoryTier::UserProfile,
                        _ => crate::tui::memory_browser::MemoryTier::LongTerm,
                    };
                    crate::tui::memory_browser::MemoryEntry {
                        id: v.get("id").and_then(|i| i.as_str()).unwrap_or("").to_string(),
                        content,
                        tier,
                        category: v.get("category").and_then(|c| c.as_str()).unwrap_or("general").to_string(),
                        created_at: v.get("created_at").and_then(|c| c.as_f64()).unwrap_or(0.0),
                        updated_at: v.get("updated_at").and_then(|u| u.as_f64()).unwrap_or(0.0),
                        access_count: v.get("access_count").and_then(|a| a.as_u64()).unwrap_or(0) as usize,
                        score: v.get("score").and_then(|s| s.as_f64()).unwrap_or(0.0),
                    }
                }).collect();
                self.memory_browser.set_entries(entries, result.count);
                Command::None
            }
            AppEvent::MemoryStats { stats } => {
                if let Some(total) = stats.get("total_entries").and_then(|t| t.as_u64()) {
                    self.memory_browser.total_count = total as usize;
                }
                Command::None
            }
        }
    }

    /// Called every 16ms (60fps tick).
    fn on_tick(&mut self) -> Command {
        self.refresh_resources();
        Command::None
    }

    /// Handle an ACP streaming event from the backend.
    fn on_acp_event(&mut self, method: &str, params: Option<&serde_json::Value>) {
        match method {
            "content_chunk" => {
                if let Some(text) = params
                    .and_then(|p| p.get("data"))
                    .and_then(|d| d.as_str())
                {
                    self.stream_buffer.push_str(text);
                    // Feed block detector for streaming state
                    for ch in text.chars() {
                        self.block_detector.feed(ch);
                    }
                    // Create or update the AssistantResponse message
                    let has_assistant_msg = self
                        .messages
                        .last()
                        .map(|m| m.kind == MessageKind::AssistantResponse)
                        .unwrap_or(false);
                    if has_assistant_msg {
                        if let Some(last) = self.messages.last_mut() {
                            last.content.push_str(text);
                        }
                    } else {
                        // First chunk — create the initial message
                        self.messages.push(ChatMessage {
                            kind: MessageKind::AssistantResponse,
                            content: text.to_string(),
                            timestamp: Instant::now(),
                        });
                    }
                }
            }
            "content_complete" => {
                let content = std::mem::take(&mut self.stream_buffer);
                if !content.is_empty() {
                    // Update or create the final assistant message
                    let has_assistant_msg = self
                        .messages
                        .last()
                        .map(|m| m.kind == MessageKind::AssistantResponse)
                        .unwrap_or(false);
                    if has_assistant_msg {
                        if let Some(last) = self.messages.last_mut() {
                            last.content = content;
                        }
                    } else {
                        self.messages.push(ChatMessage {
                            kind: MessageKind::AssistantResponse,
                            content,
                            timestamp: Instant::now(),
                        });
                    }
                }
                if self.phase == AppPhase::Processing {
                    self.phase = AppPhase::Ready;
                }
            }
            "thinking" => {
                if let Some(text) = params
                    .and_then(|p| p.get("data"))
                    .and_then(|d| d.as_str())
                {
                    self.add_thinking_message(text);
                }
            }
            "tool_call" => {
                if let Some(data) = params.and_then(|p| p.get("data")) {
                    let name = data
                        .get("name")
                        .and_then(|n| n.as_str())
                        .unwrap_or("unknown");
                    self.add_tool_call_message(name, &data.to_string());
                }
            }
            "tool_result" => {
                if let Some(data) = params.and_then(|p| p.get("data")) {
                    let name = data
                        .get("name")
                        .and_then(|n| n.as_str())
                        .unwrap_or("unknown");
                    let output = data
                        .get("output")
                        .and_then(|o| o.as_str())
                        .unwrap_or("");
                    let success = data
                        .get("success")
                        .and_then(|s| s.as_bool())
                        .unwrap_or(false);
                    self.add_tool_result_message(name, output, success);
                }
            }
            "state_change" => {
                if let Some(text) = params
                    .and_then(|p| p.get("data"))
                    .and_then(|d| d.as_str())
                {
                    self.agent_state = text.to_string();
                }
            }
            "error" => {
                if let Some(text) = params
                    .and_then(|p| p.get("data"))
                    .and_then(|d| d.as_str())
                {
                    self.add_error_message(text);
                    if self.phase == AppPhase::Processing {
                        self.phase = AppPhase::Ready;
                    }
                }
            }
            "done" if self.phase == AppPhase::Processing => {
                self.phase = AppPhase::Ready;
            }
            _ => {
                // Unknown event type — ignore
            }
        }
    }

    /// Handle a keyboard key press event.
    fn on_key(&mut self, key: crossterm::event::KeyEvent) -> Command {
        use crossterm::event::{KeyCode, KeyModifiers};

        // Global keybindings (work in all modes)
        if key.modifiers == KeyModifiers::CONTROL {
            match key.code {
                KeyCode::Char('c') => {
                    if self.phase == AppPhase::Processing {
                        // Show interrupt dialog — don't send /stop yet
                        self.phase = AppPhase::Interrupted;
                        self.interrupt_action = None;
                        return Command::None;
                    }
                    return Command::None;
                }
                KeyCode::Char('t') => return Command::ToggleInspector,
                KeyCode::Char('p') => return Command::TogglePalette,
                KeyCode::Char('m') => return Command::ToggleMemoryBrowser,
                KeyCode::Char('d') => {
                    self.phase = AppPhase::Exiting;
                    self.should_quit = true;
                    return Command::Quit;
                }
                KeyCode::Char('l') => {
                    return Command::CycleLayout;
                }
                KeyCode::Char('k') => {
                    // Clear chat
                    self.messages.clear();
                    self.stream_buffer.clear();
                    return Command::None;
                }
                _ => {}
            }
        }

        // Interrupted phase — only C/R/Esc keys work
        if self.phase == AppPhase::Interrupted {
            match key.code {
                KeyCode::Char('c' | 'C') => {
                    // Cancel: go back to ready, discard current execution
                    self.phase = AppPhase::Ready;
                    self.interrupt_action = Some(InterruptAction::Cancel);
                    return Command::InterruptAgent;
                }
                KeyCode::Char('r' | 'R') => {
                    // Redirect: stay in processing, allow new input
                    return Command::None;
                }
                KeyCode::Esc => {
                    // Continue: return to processing
                    self.phase = AppPhase::Processing;
                    self.interrupt_action = None;
                    return Command::None;
                }
                _ => return Command::None,
            }
        }

            // Esc: close modals or cancel
        if key.code == KeyCode::Esc {
            if self.inspector_visible {
                self.inspector_visible = false;
                return Command::None;
            }
            if self.palette_open {
                self.palette_open = false;
                return Command::None;
            }
            return Command::None;
        }

        // Tab: cycle focus or cycle inspector panels
        if key.code == KeyCode::Tab {
            if self.inspector_visible {
                let panels = InspectorPanel::ALL;
                let current = panels.iter().position(|p| *p == self.inspector_tab).unwrap_or(0);
                self.inspector_tab = panels[(current + 1) % panels.len()];
                return Command::None;
            }
            self.focused_pane = (self.focused_pane + 1) % 3;
            return Command::None;
        }

        // Shift+Tab: reverse cycle inspector panels
        if key.code == KeyCode::BackTab {
            if self.inspector_visible {
                let panels = InspectorPanel::ALL;
                let current = panels.iter().position(|p| *p == self.inspector_tab).unwrap_or(0);
                self.inspector_tab = panels[(current + panels.len() - 1) % panels.len()];
                return Command::None;
            }
            return Command::None;
        }

        // PageUp/PageDown: scroll chat pane
        match key.code {
            KeyCode::PageUp => {
                self.chat_scroll = self.chat_scroll.saturating_add(10);
                return Command::None;
            }
            KeyCode::PageDown => {
                self.chat_scroll = self.chat_scroll.saturating_sub(10);
                return Command::None;
            }
            _ => {}
        }

        // Input bar is focused by default (pane 0)
        if self.focused_pane == 0 {
            self.handle_input_key(key)
        } else {
            Command::None
        }
    }

    /// Handle key events when the input bar is focused.
    fn handle_input_key(&mut self, key: crossterm::event::KeyEvent) -> Command {
        use crossterm::event::{KeyCode, KeyModifiers};

        match key.code {
            KeyCode::Enter => {
                let input = std::mem::take(&mut self.input_buffer);
                let trimmed = input.trim().to_string();
                self.input_cursor = 0;

                if trimmed.is_empty() {
                    return Command::None;
                }

                // Add to history
                if self.input_history.last() != Some(&trimmed) {
                    self.input_history.push(trimmed.clone());
                    if self.input_history.len() > 100 {
                        self.input_history.remove(0);
                    }
                }
                self.input_history_pos = None;

                // Handle built-in commands
                if trimmed.starts_with('/') {
                    let cmd = trimmed.to_lowercase();
                    match cmd.as_str() {
                        "/quit" | "/exit" => {
                            self.phase = AppPhase::Exiting;
                            self.should_quit = true;
                            return Command::Quit;
                        }
                        "/clear" => {
                            self.messages.clear();
                            self.stream_buffer.clear();
                            return Command::None;
                        }
                        _ => {
                            // Forward to backend as a command
                        }
                    }
                }

                // Add user message to display
                self.add_user_message(&trimmed);
                self.phase = AppPhase::Processing;
                self.agent_state = "thinking".to_string();

                Command::SendAcp(trimmed)
            }
            KeyCode::Backspace => {
                if self.input_cursor > 0 {
                    let idx = self.input_cursor - 1;
                    self.input_buffer.remove(idx);
                    self.input_cursor -= 1;
                }
                Command::None
            }
            KeyCode::Delete => {
                if self.input_cursor < self.input_buffer.len() {
                    self.input_buffer.remove(self.input_cursor);
                }
                Command::None
            }
            KeyCode::Left => {
                self.input_cursor = self.input_cursor.saturating_sub(1);
                Command::None
            }
            KeyCode::Right => {
                if self.input_cursor < self.input_buffer.len() {
                    self.input_cursor += 1;
                }
                Command::None
            }
            KeyCode::Home => {
                self.input_cursor = 0;
                Command::None
            }
            KeyCode::End => {
                self.input_cursor = self.input_buffer.len();
                Command::None
            }
            KeyCode::Up => {
                // History navigation
                let pos = match self.input_history_pos {
                    Some(p) if p > 0 => p - 1,
                    None if !self.input_history.is_empty() => self.input_history.len() - 1,
                    _ => return Command::None,
                };
                self.input_history_pos = Some(pos);
                self.input_buffer = self.input_history[pos].clone();
                self.input_cursor = self.input_buffer.len();
                Command::None
            }
            KeyCode::Down => {
                if let Some(pos) = self.input_history_pos {
                    if pos + 1 < self.input_history.len() {
                        let new_pos = pos + 1;
                        self.input_history_pos = Some(new_pos);
                        self.input_buffer = self.input_history[new_pos].clone();
                    } else {
                        self.input_history_pos = None;
                        self.input_buffer.clear();
                    }
                    self.input_cursor = self.input_buffer.len();
                }
                Command::None
            }
            KeyCode::Char(c) if key.modifiers == KeyModifiers::CONTROL => {
                match c {
                    'a' => self.input_cursor = 0,
                    'e' => self.input_cursor = self.input_buffer.len(),
                    'w' => {
                        // Delete word before cursor
                        let before = &self.input_buffer[..self.input_cursor];
                        let after = &self.input_buffer[self.input_cursor..];
                        let trimmed_before = before.trim_end_matches(|c: char| c.is_whitespace());
                        let word_boundary = trimmed_before
                            .rfind(|c: char| c.is_whitespace())
                            .map(|i| i + 1)
                            .unwrap_or(0);
                        self.input_buffer = before[..word_boundary].to_string() + after;
                        self.input_cursor = word_boundary;
                    }
                    'u' => {
                        self.input_buffer.clear();
                        self.input_cursor = 0;
                    }
                    _ => {}
                }
                Command::None
            }
            KeyCode::Char(c) => {
                let idx = self.input_cursor;
                self.input_buffer.insert(idx, c);
                self.input_cursor += 1;
                Command::None
            }
            KeyCode::Tab => {
                // Basic tab → 2-space indent
                let idx = self.input_cursor;
                self.input_buffer.insert_str(idx, "  ");
                self.input_cursor += 2;
                Command::None
            }
            _ => Command::None,
        }
    }

    /// Cycle through available layout presets.
    pub fn cycle_layout(&mut self) {
        let presets = ["minimal", "developer", "researcher", "orchestrator", "monitor"];
        let current = presets.iter().position(|p| *p == self.layout).unwrap_or(0);
        let next = (current + 1) % presets.len();
        self.layout = presets[next].to_string();
    }

    // ── Message helpers ─────────────────────────────────────────────

    pub fn add_user_message(&mut self, text: &str) {
        self.messages.push(ChatMessage {
            kind: MessageKind::UserInput,
            content: text.to_string(),
            timestamp: Instant::now(),
        });
        // Trim buffer to 500 messages
        if self.messages.len() > 500 {
            self.messages.remove(0);
        }
    }

    pub fn add_system_message(&mut self, text: &str) {
        self.messages.push(ChatMessage {
            kind: MessageKind::System,
            content: text.to_string(),
            timestamp: Instant::now(),
        });
    }

    fn add_thinking_message(&mut self, text: &str) {
        self.messages.push(ChatMessage {
            kind: MessageKind::Thinking,
            content: format!("◦ {text}"),
            timestamp: Instant::now(),
        });
    }

    fn add_tool_call_message(&mut self, name: &str, args: &str) {
        let preview = if args.len() > 80 {
            format!("{}...", &args[..80])
        } else {
            args.to_string()
        };
        self.messages.push(ChatMessage {
            kind: MessageKind::ToolCall,
            content: format!("⚙ {name}({preview})"),
            timestamp: Instant::now(),
        });
    }

    fn add_tool_result_message(&mut self, name: &str, output: &str, success: bool) {
        let preview = if output.len() > 100 {
            format!("{}...", &output[..100])
        } else {
            output.to_string()
        };
        let icon = if success { "✓" } else { "✗" };
        self.messages.push(ChatMessage {
            kind: MessageKind::ToolResult,
            content: format!("{icon} {name}: {preview}"),
            timestamp: Instant::now(),
        });
    }

    fn add_error_message(&mut self, text: &str) {
        self.messages.push(ChatMessage {
            kind: MessageKind::Error,
            content: format!("✗ {text}"),
            timestamp: Instant::now(),
        });
    }

    /// Get session uptime as a formatted string.
    pub fn uptime_string(&self) -> String {
        let elapsed = self.session_start.elapsed();
        let secs = elapsed.as_secs();
        if secs < 60 {
            format!("{secs}s")
        } else if secs < 3600 {
            format!("{}m {}s", secs / 60, secs % 60)
        } else {
            format!("{}h {}m", secs / 3600, (secs % 3600) / 60)
        }
    }

    /// Update config after init response.
    pub fn set_session_info(&mut self, model: &str, provider: &str, effort: &str) {
        self.model_name = model.to_string();
        self.provider_name = provider.to_string();
        self.effort_level = effort.to_string();
    }
}
