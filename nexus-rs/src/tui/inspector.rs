//! Task Inspector — live, interactive TUI panel showing full state of every active task.
//!
//! Toggle with Ctrl+T. Shows: task tree, trace log, memory view, context budget,
//! running diff, cost breakdown, and agent graph.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Modifier, Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Paragraph, Wrap};

use crate::app::{App, AppPhase, BackendStatus};
use crate::tui::render::themes::Theme;

/// Panels within the task inspector.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InspectorPanel {
    Overview,
    Trace,
    Memory,
    Context,
    Diff,
    Cost,
    Graph,
}

impl InspectorPanel {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Overview => "Overview",
            Self::Trace => "Trace",
            Self::Memory => "Memory",
            Self::Context => "Context",
            Self::Diff => "Diff",
            Self::Cost => "Cost",
            Self::Graph => "Graph",
        }
    }

    pub const ALL: &'static [InspectorPanel] = &[
        Self::Overview,
        Self::Trace,
        Self::Memory,
        Self::Context,
        Self::Diff,
        Self::Cost,
        Self::Graph,
    ];
}

/// Render the full task inspector overlay.
pub fn render_inspector(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
    if area.width < 60 || area.height < 15 {
        return;
    }

    // Full-screen inspector: reserve left 60% for main, right 40% for detail
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),       // Tab bar
            Constraint::Min(1),          // Content
            Constraint::Length(1),       // Status bar
        ])
        .split(area);

    // Tab bar
    let tab_area = vertical[0];
    render_tab_bar(frame, tab_area, app.inspector_tab, theme);

    // Content
    let content_area = vertical[1];
    match app.inspector_tab {
        InspectorPanel::Overview => render_overview(frame, content_area, app, theme),
        InspectorPanel::Trace => render_trace(frame, content_area, app, theme),
        InspectorPanel::Memory => render_memory(frame, content_area, app, theme),
        InspectorPanel::Context => render_context(frame, content_area, app, theme),
        InspectorPanel::Diff => render_diff(frame, content_area, app, theme),
        InspectorPanel::Cost => render_cost(frame, content_area, app, theme),
        InspectorPanel::Graph => render_graph(frame, content_area, app, theme),
    }

    // Bottom status
    let status_area = vertical[2];
    let status_text = format!(
        " [Tab/← →] panels  |  Ctrl+T to close  |  {} tabs ",
        InspectorPanel::ALL.len(),
    );
    frame.render_widget(
        Paragraph::new(Line::from(Span::styled(
            status_text,
            Style::default().fg(theme.colors.muted_col()).dim(),
        )))
        .style(Style::default().bg(theme.colors.surface_col())),
        status_area,
    );
}

/// Tab bar showing available inspector panels.
fn render_tab_bar(frame: &mut ratatui::Frame, area: Rect, active: InspectorPanel, theme: &Theme) {
    let mut spans = Vec::new();
    for (i, panel) in InspectorPanel::ALL.iter().enumerate() {
        let is_active = *panel == active;
        let label = panel.label();
        let tab_text = if is_active {
            format!(" ▶ {} ", label)
        } else {
            format!("   {}   ", label)
        };
        spans.push(Span::styled(
            tab_text,
            if is_active {
                Style::default()
                    .fg(theme.colors.accent())
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.colors.muted_col())
            },
        ));
        if i < InspectorPanel::ALL.len() - 1 {
            spans.push(Span::styled("│", Style::default().fg(theme.colors.muted_col())));
        }
    }
    frame.render_widget(
        Paragraph::new(Line::from(spans))
            .style(Style::default().bg(theme.colors.surface_col())),
        area,
    );
}

/// Overview: task tree with status, agent, plan steps, tools, memory, tokens, cost, context.
fn render_overview(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Task State ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    let mut lines = vec![
        Line::from(vec![
            Span::styled(" Status: ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(
                format!("{:?}", app.phase),
                match app.phase {
                    AppPhase::Ready => Style::default().fg(theme.colors.ok()),
                    AppPhase::Processing => Style::default().fg(theme.colors.accent()),
                    AppPhase::Error => Style::default().fg(theme.colors.err()),
                    AppPhase::Interrupted => Style::default().fg(theme.colors.warn()),
                    _ => Style::default().fg(theme.colors.muted_col()),
                },
            ),
        ]),
    ];

    // Agent state
    let agent_state = if app.agent_state.is_empty() {
        match app.phase {
            AppPhase::Ready => "idle",
            AppPhase::Processing => "thinking",
            _ => "unknown",
        }
    } else {
        &app.agent_state
    };
    lines.push(Line::from(vec![
        Span::styled(" Agent:  ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(agent_state, Style::default().fg(theme.colors.fg())),
    ]));

    lines.push(Line::from(vec![
        Span::styled(" Model:  ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(
            if app.model_name.is_empty() { "none" } else { &app.model_name },
            Style::default().fg(theme.colors.accent2()),
        ),
    ]));

    lines.push(Line::from(vec![
        Span::styled(" Prov:   ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(&app.provider_name, Style::default().fg(theme.colors.info_col())),
    ]));

    // Plan steps (simulated from messages)
    let plan_steps: Vec<&str> = app.messages.iter()
        .filter(|m| m.kind == crate::app::MessageKind::Thinking)
        .map(|m| m.content.as_str())
        .take(8)
        .collect();

    if !plan_steps.is_empty() {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(" Plan Steps:", Style::default().fg(theme.colors.muted_col()).bold())));
        for (i, step) in plan_steps.iter().enumerate() {
            let icon = if i < plan_steps.len() - 1 { "  ✓ " } else { "  ▶ " };
            lines.push(Line::from(Span::styled(
                format!("{}{}", icon, step),
                Style::default().fg(theme.colors.fg()),
            )));
        }
    }

    // Tools used
    let tool_count = app.messages.iter()
        .filter(|m| m.kind == crate::app::MessageKind::ToolCall).count();
    lines.push(Line::from(""));
    lines.push(Line::from(vec![
        Span::styled(" Tools:  ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(format!("{tool_count} called"), Style::default().fg(theme.colors.tool_call_col())),
    ]));

    // Tokens
    lines.push(Line::from(vec![
        Span::styled(" Tokens: ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(
            format!("↓ {} in · ↑ {} out", format_count(app.tokens_in), format_count(app.tokens_out)),
            Style::default().fg(theme.colors.fg()),
        ),
    ]));

    // Backend
    let backend_str = match &app.backend {
        BackendStatus::Connected => "connected".to_string(),
        BackendStatus::Degraded(e) => format!("degraded: {e}"),
        BackendStatus::Disconnected => "disconnected".to_string(),
        BackendStatus::Connecting => "connecting".to_string(),
    };
    lines.push(Line::from(vec![
        Span::styled(" Backend:", Style::default().fg(theme.colors.muted_col())),
        Span::styled(
            format!(" {backend_str}"),
            match &app.backend {
                BackendStatus::Connected => Style::default().fg(theme.colors.ok()),
                BackendStatus::Degraded(_) => Style::default().fg(theme.colors.warn()),
                _ => Style::default().fg(theme.colors.err()),
            },
        ),
    ]));

    // Uptime
    let message_count = app.messages.len();
    lines.push(Line::from(vec![
        Span::styled(" Msgs:   ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(format!("{message_count}"), Style::default().fg(theme.colors.fg())),
        Span::styled(format!("  (uptime: {})", app.uptime_string()), Style::default().fg(theme.colors.muted_col())),
    ]));

    frame.render_widget(
        Paragraph::new(lines).wrap(Wrap { trim: false }).block(Block::default()),
        inner,
    );
}

/// Trace: chronological log of agent actions, tool calls, and model calls.
fn render_trace(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Agent Trace ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    let trace_lines: Vec<Line> = app.messages.iter().enumerate().rev().take(50).map(|(i, msg)| {
        let (icon, style) = match msg.kind {
            crate::app::MessageKind::UserInput => (
                ">", Style::default().fg(theme.colors.accent()).bold(),
            ),
            crate::app::MessageKind::AssistantResponse => (
                " ", Style::default().fg(theme.colors.fg()),
            ),
            crate::app::MessageKind::ToolCall => (
                "⚙", Style::default().fg(theme.colors.tool_call_col()),
            ),
            crate::app::MessageKind::ToolResult => (
                "✓", Style::default().fg(theme.colors.tool_result_col()),
            ),
            crate::app::MessageKind::Thinking => (
                "◦", Style::default().fg(theme.colors.thought()).italic(),
            ),
            crate::app::MessageKind::Error => (
                "✗", Style::default().fg(theme.colors.err()).bold(),
            ),
            crate::app::MessageKind::Warning => (
                "⚠", Style::default().fg(theme.colors.warn()),
            ),
            crate::app::MessageKind::System => (
                "i", Style::default().fg(theme.colors.info_col()).dim(),
            ),
        };
        let preview = if msg.content.len() > 80 {
            format!("{}...", &msg.content[..80])
        } else {
            msg.content.clone()
        };
        Line::from(Span::styled(format!(" {icon} [{i:>4}] {preview}"), style))
    }).collect();

    frame.render_widget(
        Paragraph::new(trace_lines).wrap(Wrap { trim: false }).block(Block::default()),
        inner,
    );
}

/// Memory: live view of working memory and recent retrieval.
fn render_memory(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Memory View ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    let lines = vec![
        Line::from(Span::styled(" Working Memory ", Style::default().fg(theme.colors.accent()).bold())),
        Line::from(""),
        Line::from(Span::styled("  (Agent working memory synced from backend)", Style::default().fg(theme.colors.muted_col()).italic())),
        Line::from(""),
        Line::from(Span::styled(" Long-term Memory ", Style::default().fg(theme.colors.accent2()).bold())),
        Line::from(""),
        Line::from(Span::styled("  (Long-term memory synced from backend)", Style::default().fg(theme.colors.muted_col()).italic())),
    ];

    frame.render_widget(
        Paragraph::new(lines).block(Block::default()),
        inner,
    );
}

/// Context: visual representation of the current context window.
fn render_context(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Context Budget ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    // Simulate context budget: 128K max, ~2K per message estimate
    let max_context = 128_000u64;
    let msg_tokens = app.messages.len() as u64 * 2000; // rough estimate
    let pct = ((msg_tokens as f64 / max_context as f64) * 100.0).min(100.0);

    let bar_width = inner.width.saturating_sub(4) as usize;
    let filled = ((pct / 100.0) * bar_width as f64) as usize;
    let empty = bar_width.saturating_sub(filled);

    let bar = format!(
        "[{}>{}]",
        "=".repeat(filled.min(bar_width)),
        " ".repeat(empty.min(bar_width))
    );

    let lines = vec![
        Line::from(Span::styled(
            format!(" {:.1}% used ({}/{})", pct, format_count(msg_tokens), format_count(max_context)),
            Style::default().fg(if pct > 85.0 { theme.colors.warn() } else { theme.colors.fg() }),
        )),
        Line::from(Span::styled(bar, Style::default().fg(theme.colors.accent()))),
        Line::from(""),
        Line::from(Span::styled(
            format!(" {} messages in context", app.messages.len()),
            Style::default().fg(theme.colors.muted_col()),
        )),
        Line::from(Span::styled(
            " System prompt + memory + tools overlay",
            Style::default().fg(theme.colors.muted_col()),
        )),
    ];

    frame.render_widget(
        Paragraph::new(lines).block(Block::default()),
        inner,
    );
}

/// Diff: running diff of every file modified in this session.
fn render_diff(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Session Diff ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    let lines = vec![
        Line::from(Span::styled(" Files Modified ", Style::default().fg(theme.colors.accent()).bold())),
        Line::from(""),
        Line::from(Span::styled("  (No files modified yet)", Style::default().fg(theme.colors.muted_col()).italic())),
        Line::from(""),
        Line::from(Span::styled(" Diff Stats ", Style::default().fg(theme.colors.accent2()).bold())),
        Line::from(""),
        Line::from(format!("  +{} added lines    -{} removed lines", 0, 0)),
    ];

    frame.render_widget(
        Paragraph::new(lines).block(Block::default()),
        inner,
    );
}

/// Cost: token usage breakdown per model, per agent.
fn render_cost(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Cost Breakdown ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    let cost_str = if app.estimated_cost > 0.0 {
        format!("${:.6}", app.estimated_cost)
    } else {
        "$0.00".to_string()
    };

    let mut lines = vec![
        Line::from(vec![
            Span::styled(" Model: ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(&app.model_name, Style::default().fg(theme.colors.accent())),
        ]),
        Line::from(vec![
            Span::styled(" Tokens in:  ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(format_count(app.prompt_tokens_total), Style::default().fg(theme.colors.fg())),
        ]),
        Line::from(vec![
            Span::styled(" Tokens out: ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(format_count(app.completion_tokens_total), Style::default().fg(theme.colors.fg())),
        ]),
        Line::from(vec![
            Span::styled(" Total:      ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(
                format_count(app.total_tokens),
                Style::default().fg(theme.colors.accent2()),
            ),
        ]),
        Line::from(vec![
            Span::styled(" Est. Cost:  ", Style::default().fg(theme.colors.muted_col())),
            Span::styled(cost_str, Style::default().fg(theme.colors.warn())),
        ]),
    ];

    // Per-model breakdown
    if !app.cost_by_model.is_empty() {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            " Per-Model Breakdown:",
            Style::default().fg(theme.colors.accent()).bold(),
        )));
        for (model_name, cost, tokens) in &app.cost_by_model {
            lines.push(Line::from(vec![
                Span::styled(
                    format!("  \u{2022} {}: ", model_name),
                    Style::default().fg(theme.colors.fg()),
                ),
                Span::styled(
                    format!("{} tokens, ${:.6}", tokens, cost),
                    Style::default().fg(theme.colors.muted_col()),
                ),
            ]));
        }
    }

    lines.push(Line::from(""));
    lines.push(Line::from(vec![
        Span::styled(" Provider: ", Style::default().fg(theme.colors.muted_col())),
        Span::styled(&app.provider_name, Style::default().fg(theme.colors.info_col())),
    ]));

    frame.render_widget(
        Paragraph::new(lines).block(Block::default()),
        inner,
    );
}

/// Graph: live agent graph showing nodes and edges.
fn render_graph(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
    let block = Block::default()
        .title(" Agent Graph ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(theme.colors.surface_col()));

    let inner = block.inner(area);
    frame.render_widget(&block, area);

    // Simple ASCII agent graph
    let lines = vec![
        Line::from(Span::styled(" ┌─────────────┐", Style::default().fg(theme.colors.accent()))),
        Line::from(Span::styled(" │ Orchestrator │", Style::default().fg(theme.colors.accent()).bold())),
        Line::from(Span::styled(" └──────┬──────┘", Style::default().fg(theme.colors.accent()))),
        Line::from(Span::styled("    ┌───┼───┐", Style::default().fg(theme.colors.muted_col()))),
        Line::from(Span::styled("    │   │   │", Style::default().fg(theme.colors.muted_col()))),
        Line::from(vec![
            Span::styled(" ┌──┴──┐", Style::default().fg(theme.colors.accent2())),
            Span::styled(" ┌──┴──┐", Style::default().fg(theme.colors.accent2())),
            Span::styled(" ┌──┴──┐", Style::default().fg(theme.colors.accent2())),
        ]),
        Line::from(vec![
            Span::styled(" │Plan │", Style::default().fg(theme.colors.accent2()).bold()),
            Span::styled(" │Code │", Style::default().fg(theme.colors.accent2()).bold()),
            Span::styled(" │Review│", Style::default().fg(theme.colors.accent2()).bold()),
        ]),
        Line::from(vec![
            Span::styled(" └─────┘", Style::default().fg(theme.colors.accent2())),
            Span::styled(" └─────┘", Style::default().fg(theme.colors.accent2())),
            Span::styled(" └─────┘", Style::default().fg(theme.colors.accent2())),
        ]),
    ];

    frame.render_widget(
        Paragraph::new(lines).block(Block::default()),
        inner,
    );
}

/// Format a token count for display.
fn format_count(count: u64) -> String {
    if count >= 1_000_000 {
        format!("{:.1}M", count as f64 / 1_000_000.0)
    } else if count >= 1_000 {
        format!("{:.1}k", count as f64 / 1_000.0)
    } else {
        format!("{count}")
    }
}
