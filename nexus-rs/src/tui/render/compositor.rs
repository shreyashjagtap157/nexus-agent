//! TUI Compositor — multi-pane layout engine with layout presets.
//!
//! Manages the spatial arrangement of panes (chat, diff, memory, inspector,
//! resource monitor, agent graph) and provides layout presets.

use ratatui::layout::{Constraint, Direction, Layout, Rect};

// ── Layout Presets ─────────────────────────────────────────────────────

/// Available layout presets.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LayoutPreset {
    /// Single full-width chat pane + status bar.
    Minimal,
    /// Chat + file diff side-by-side.
    Developer,
    /// Chat + memory browser + web results.
    Researcher,
    /// Chat + agent graph + task inspector.
    Orchestrator,
    /// Chat + resource monitor + analytics.
    Monitor,
    /// User-defined custom layout.
    Custom,
}

impl LayoutPreset {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "developer" => Self::Developer,
            "researcher" => Self::Researcher,
            "orchestrator" => Self::Orchestrator,
            "monitor" => Self::Monitor,
            "custom" => Self::Custom,
            _ => Self::Minimal,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Minimal => "minimal",
            Self::Developer => "developer",
            Self::Researcher => "researcher",
            Self::Orchestrator => "orchestrator",
            Self::Monitor => "monitor",
            Self::Custom => "custom",
        }
    }

    /// All presets for cycling.
    pub const ALL: &'static [LayoutPreset] = &[
        Self::Minimal,
        Self::Developer,
        Self::Researcher,
        Self::Orchestrator,
        Self::Monitor,
    ];
}

// ── Pane Definitions ───────────────────────────────────────────────────

/// Identifies a pane region in the layout.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PaneId {
    StatusBar,
    Chat,
    InputBar,
    Diff,
    Memory,
    WebResults,
    AgentGraph,
    TaskInspector,
    ResourceMonitor,
    Analytics,
    FileTree,
}

/// Result of computing a layout for a given screen area.
#[derive(Debug, Clone)]
pub struct LayoutResult {
    pub status_bar: Rect,
    pub chat: Rect,
    pub input_bar: Rect,
    pub diff: Option<Rect>,
    pub memory: Option<Rect>,
    pub web_results: Option<Rect>,
    pub agent_graph: Option<Rect>,
    pub task_inspector: Option<Rect>,
    pub resource_monitor: Option<Rect>,
    pub analytics: Option<Rect>,
    pub file_tree: Option<Rect>,
}

impl LayoutResult {
    pub fn get(&self, pane: PaneId) -> Option<Rect> {
        match pane {
            PaneId::StatusBar => Some(self.status_bar),
            PaneId::Chat => Some(self.chat),
            PaneId::InputBar => Some(self.input_bar),
            PaneId::Diff => self.diff,
            PaneId::Memory => self.memory,
            PaneId::WebResults => self.web_results,
            PaneId::AgentGraph => self.agent_graph,
            PaneId::TaskInspector => self.task_inspector,
            PaneId::ResourceMonitor => self.resource_monitor,
            PaneId::Analytics => self.analytics,
            PaneId::FileTree => self.file_tree,
        }
    }
}

/// Compute the layout for a given preset and screen area.
pub fn compute_layout(area: Rect, preset: LayoutPreset) -> LayoutResult {
    match preset {
        LayoutPreset::Minimal => layout_minimal(area),
        LayoutPreset::Developer => layout_developer(area),
        LayoutPreset::Researcher => layout_researcher(area),
        LayoutPreset::Orchestrator => layout_orchestrator(area),
        LayoutPreset::Monitor => layout_monitor(area),
        LayoutPreset::Custom => layout_minimal(area),
    }
}

// ── Preset Layouts ─────────────────────────────────────────────────────

/// Minimal: single chat pane.
fn layout_minimal(area: Rect) -> LayoutResult {
    let main = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),    // Status bar
            Constraint::Min(3),       // Chat
            Constraint::Length(3),    // Input bar
        ])
        .split(area);

    LayoutResult {
        status_bar: main[0],
        chat: main[1],
        input_bar: main[2],
        diff: None,
        memory: None,
        web_results: None,
        agent_graph: None,
        task_inspector: None,
        resource_monitor: None,
        analytics: None,
        file_tree: None,
    }
}

/// Developer: chat + diff side-by-side.
fn layout_developer(area: Rect) -> LayoutResult {
    let top_bottom = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),    // Status bar
            Constraint::Min(3),       // Main content
            Constraint::Length(3),    // Input bar
        ])
        .split(area);

    let content = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(50),  // Chat
            Constraint::Percentage(50),  // Diff
        ])
        .split(top_bottom[1]);

    LayoutResult {
        status_bar: top_bottom[0],
        chat: content[0],
        input_bar: top_bottom[2],
        diff: Some(content[1]),
        memory: None,
        web_results: None,
        agent_graph: None,
        task_inspector: None,
        resource_monitor: None,
        analytics: None,
        file_tree: None,
    }
}

/// Researcher: chat + memory + web results.
fn layout_researcher(area: Rect) -> LayoutResult {
    let top_bottom = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(3),
        ])
        .split(area);

    let content = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(40),  // Chat
            Constraint::Percentage(30),  // Memory
            Constraint::Percentage(30),  // Web results
        ])
        .split(top_bottom[1]);

    LayoutResult {
        status_bar: top_bottom[0],
        chat: content[0],
        input_bar: top_bottom[2],
        diff: None,
        memory: Some(content[1]),
        web_results: Some(content[2]),
        agent_graph: None,
        task_inspector: None,
        resource_monitor: None,
        analytics: None,
        file_tree: None,
    }
}

/// Orchestrator: chat + agent graph + task inspector.
fn layout_orchestrator(area: Rect) -> LayoutResult {
    let top_bottom = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(3),
        ])
        .split(area);

    let content = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(40),  // Chat
            Constraint::Percentage(30),  // Agent graph
            Constraint::Percentage(30),  // Task inspector
        ])
        .split(top_bottom[1]);

    LayoutResult {
        status_bar: top_bottom[0],
        chat: content[0],
        input_bar: top_bottom[2],
        diff: None,
        memory: None,
        web_results: None,
        agent_graph: Some(content[1]),
        task_inspector: Some(content[2]),
        resource_monitor: None,
        analytics: None,
        file_tree: None,
    }
}

/// Monitor: chat + resource monitor + analytics.
fn layout_monitor(area: Rect) -> LayoutResult {
    let top_bottom = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(3),
        ])
        .split(area);

    let content = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(45),  // Chat
            Constraint::Percentage(30),  // Resource monitor
            Constraint::Percentage(25),  // Analytics
        ])
        .split(top_bottom[1]);

    LayoutResult {
        status_bar: top_bottom[0],
        chat: content[0],
        input_bar: top_bottom[2],
        diff: None,
        memory: None,
        web_results: None,
        agent_graph: None,
        task_inspector: None,
        resource_monitor: Some(content[1]),
        analytics: Some(content[2]),
        file_tree: None,
    }
}
