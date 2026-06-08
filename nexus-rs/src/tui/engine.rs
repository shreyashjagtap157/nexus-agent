//! TUI engine — manages the crossterm raw-mode render loop.
//!
//! Responsibilities:
//! - Enter/exit crossterm raw mode
//! - 60fps render loop using Ratatui terminal
//! - Read keyboard events via crossterm event polling
//! - Route events to App model via channel
//! - Handle window resize
//! - Draw frame using the render pipeline (compositor → theme → block renderer)
//!
//! Render pipeline:
//! 1. Compute layout from active preset (compositor)
//! 2. Apply theme colors/icons/borders
//! 3. Render each pane through content-type formatter
//! 4. Render overlays (inspector, palette, interrupt dialog)

use std::io::Stdout;
use std::time::Duration;

use crossterm::terminal::{self, EnterAlternateScreen, LeaveAlternateScreen};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::Rect;
use ratatui::style::{Modifier, Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Paragraph, Scrollbar, ScrollbarOrientation, ScrollbarState, Wrap};
use ratatui::Terminal;
use tokio::sync::mpsc;

use crossterm::event::{self, Event, KeyEventKind};

use crate::app::{App, AppEvent, AppPhase, BackendStatus, MessageKind};
use crate::tui::inspector;
use crate::tui::render::blocks::{BlockDetector, BlockType};
use crate::tui::render::compositor::{self, LayoutPreset};
use crate::tui::render::themes::Theme;

/// Channel capacity for events from the TUI engine to the main loop.
const EVENT_CHANNEL_SIZE: usize = 64;

/// How often to poll for keyboard events (ms).
const KEY_POLL_INTERVAL_MS: u64 = 16;

/// Maximum number of scrollback lines in the chat pane.
const MAX_CHAT_LINES: usize = 1000;

/// TUI engine — owns the terminal, render loop, and event channel.
pub struct TuiEngine {
    /// Ratatui terminal handle.
    terminal: Terminal<CrosstermBackend<Stdout>>,
    /// Sender for events to the main loop.
    pub event_tx: mpsc::Sender<AppEvent>,
    /// Whether the engine should keep running.
    running: bool,
}

impl TuiEngine {
    /// Create a new TUI engine and enter raw mode.
    pub fn new() -> Result<(Self, mpsc::Receiver<AppEvent>), String> {
        terminal::enable_raw_mode()
            .map_err(|e| format!("Failed to enable raw mode: {e}"))?;

        let mut stdout = std::io::stdout();
        crossterm::execute!(stdout, EnterAlternateScreen)
            .map_err(|e| format!("Failed to enter alternate screen: {e}"))?;

        let backend = CrosstermBackend::new(stdout);
        let terminal = Terminal::new(backend)
            .map_err(|e| format!("Failed to create terminal: {e}"))?;

        let (event_tx, event_rx) = mpsc::channel(EVENT_CHANNEL_SIZE);

        Ok((
            Self {
                terminal,
                event_tx,
                running: true,
            },
            event_rx,
        ))
    }

    /// Run the main event loop — polls for keyboard events, sends them
    /// through the event channel, and renders frames at 60fps.
    pub async fn run_event_loop(tx: mpsc::Sender<AppEvent>) {
        while !tx.is_closed() {
            if event::poll(Duration::from_millis(KEY_POLL_INTERVAL_MS)).unwrap_or(false) {
                if let Ok(event) = event::read() {
                    match event {
                        Event::Key(key)
                            if key.kind == KeyEventKind::Press || key.kind == KeyEventKind::Repeat =>
                        {
                            let _ = tx.send(AppEvent::KeyPressed(key)).await;
                        }
                        Event::Resize(width, height) => {
                            let _ = tx.send(AppEvent::Resized { width, height }).await;
                        }
                        _ => {}
                    }
                }
            }
            let _ = tx.send(AppEvent::Tick).await;
            tokio::time::sleep(Duration::from_millis(16)).await;
        }
    }

    /// Draw the current App state using the full render pipeline.
    pub fn draw(&mut self, app: &App) -> Result<(), String> {
        let theme = &app.theme;
        self.terminal
            .draw(|frame| {
                let area = frame.area();

                // 1. Compute layout from active preset via compositor
                let preset = LayoutPreset::from_str(&app.layout);
                let layout = compositor::compute_layout(area, preset);

                // 2. Draw each pane with theme applied
                Self::render_status_bar(frame, layout.status_bar, app, theme);
                Self::render_chat_pane(frame, layout.chat, app, theme);

                // Draw extra panes from compositor
                if let Some(diff_area) = layout.diff {
                    Self::render_diff_pane(frame, diff_area, app, theme);
                }
                if let Some(mem_area) = layout.memory {
                    Self::render_memory_pane(frame, mem_area, app, theme);
                }
                if let Some(graph_area) = layout.agent_graph {
                    Self::render_agent_graph_pane(frame, graph_area, app, theme);
                }
                if let Some(monitor_area) = layout.resource_monitor {
                    Self::render_resource_monitor(frame, monitor_area, app, theme);
                }
                if let Some(analytics_area) = layout.analytics {
                    Self::render_analytics_pane(frame, analytics_area, app, theme);
                }

                // Input always at bottom
                Self::render_input_bar(frame, layout.input_bar, app, theme);

                // 3. Render overlays on top
                if app.inspector_visible {
                    Self::render_full_inspector(frame, area, app, theme);
                }
                if app.memory_browser.visible {
                    Self::render_memory_browser(frame, area, app, theme);
                }
                if app.palette_open {
                    Self::render_command_palette(frame, area, app, theme);
                }
                if app.phase == AppPhase::Interrupted {
                    Self::render_interrupt_dialog(frame, area, app, theme);
                }
            })
            .map(|_| ())
            .map_err(|e| format!("Render error: {e}"))
    }

    /// Restore the terminal to normal mode.
    pub fn restore(&mut self) -> Result<(), String> {
        self.running = false;
        let result = terminal::disable_raw_mode()
            .and_then(|()| crossterm::execute!(std::io::stdout(), LeaveAlternateScreen));
        result.map_err(|e| format!("Failed to restore terminal: {e}"))
    }

    // ── Status Bar ────────────────────────────────────────────────

    fn render_status_bar(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let bg = match &app.backend {
            BackendStatus::Connected => theme.colors.surface_col(),
            BackendStatus::Degraded(_) => theme.colors.warn(),
            BackendStatus::Disconnected | BackendStatus::Connecting => theme.colors.err(),
        };

        let status_icon = match app.phase {
            AppPhase::Starting => &theme.icons.agent,
            AppPhase::Ready => &theme.icons.agent,
            AppPhase::Processing => &theme.icons.task_running,
            AppPhase::Interrupted => &theme.icons.model,
            AppPhase::Error => &theme.icons.task_error,
            AppPhase::Exiting => &theme.icons.agent,
        };

        let phase = match app.phase {
            AppPhase::Starting => "starting",
            AppPhase::Ready => "ready",
            AppPhase::Processing => &app.agent_state,
            AppPhase::Interrupted => "interrupted",
            AppPhase::Error => "error",
            AppPhase::Exiting => "exiting",
        };

        let left = format!(
            " {status_icon} {} | {} | {} | {} ",
            if app.model_name.is_empty() { "no-model" } else { &app.model_name },
            app.provider_name,
            app.layout,
            phase,
        );

        let cost_str = if app.estimated_cost > 0.0 {
            format!("${:.4}", app.estimated_cost)
        } else {
            String::new()
        };
        let cost_part = if !cost_str.is_empty() {
            format!(" {} |", cost_str)
        } else {
            String::new()
        };
        let right = format!(
            "{} {} in / {} out | {} ",
            cost_part,
            Self::format_tokens(app.tokens_in),
            Self::format_tokens(app.tokens_out),
            app.uptime_string(),
        );

        let left_len = left.len() as u16;
        let right_len = right.len() as u16;
        let padding = area.width.saturating_sub(left_len + right_len + 2) as usize;

        let line = Line::from(vec![
            Span::styled(left, Style::default().fg(theme.colors.fg()).bg(bg)),
            Span::styled(" ".repeat(padding), Style::default().bg(bg)),
            Span::styled(right, Style::default().fg(theme.colors.fg()).bg(bg)),
        ]);

        frame.render_widget(
            Paragraph::new(line).style(Style::default().bg(bg)),
            area,
        );
    }

    // ── Chat Pane (content-type aware) ─────────────────────────────

    fn render_chat_pane(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let layout_hint = if app.inspector_visible {
            ""
        } else {
            " [Ctrl+T: Inspector] "
        };
        let title = format!(" Chat{layout_hint}");

        let block = Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme));

        let inner = block.inner(area);

        // Build chat lines with content-type-aware styling via block detector
        let lines: Vec<Line> = app.messages.iter().flat_map(|msg| {
            Self::render_message_blocks(msg, theme)
        }).collect();

        let scrollback: Vec<Line> = if lines.len() > MAX_CHAT_LINES {
            lines[lines.len() - MAX_CHAT_LINES..].to_vec()
        } else {
            lines
        };

        let paragraph = Paragraph::new(scrollback)
            .block(block)
            .scroll((app.chat_scroll as u16, 0))
            .wrap(Wrap { trim: false });

        frame.render_widget(paragraph, area);

        if app.messages.len() > inner.height as usize {
            let scrollbar = Scrollbar::new(ScrollbarOrientation::VerticalRight)
                .begin_symbol(Some("↑"))
                .end_symbol(Some("↓"));
            let mut state = ScrollbarState::new(
                app.messages.len().saturating_sub(inner.height as usize),
            ).position(app.chat_scroll);
            frame.render_stateful_widget(scrollbar, inner, &mut state);
        }
    }

    /// Render a message as one or more styled lines based on content blocks.
    fn render_message_blocks<'a>(msg: &'a crate::app::ChatMessage, theme: &'a Theme) -> Vec<Line<'a>> {
        match msg.kind {
            MessageKind::AssistantResponse => {
                // Use block detector to decompose into semantic blocks
                let mut detector = BlockDetector::new();
                for ch in msg.content.chars() {
                    detector.feed(ch);
                }
                detector.flush();
                let blocks = detector.drain_blocks();

                if blocks.is_empty() {
                    vec![Line::from(Span::styled(
                        msg.content.clone(),
                        Style::default().fg(theme.colors.fg()),
                    ))]
                } else {
                    blocks.iter().map(|block| {
                        let style = Self::block_type_style(&block.block_type, theme);
                        let prefix = Self::block_type_icon(&block.block_type, theme);
                        let text = if prefix.is_empty() {
                            block.content.clone()
                        } else {
                            format!(" {prefix} {}", block.content)
                        };
                        Line::from(Span::styled(text, style))
                    }).collect()
                }
            }
            _ => {
                vec![Self::render_message_line(msg, theme)]
            }
        }
    }

    /// Get style for a block type.
    fn block_type_style(block_type: &BlockType, theme: &Theme) -> Style {
        match block_type {
            BlockType::Prose | BlockType::System => {
                Style::default().fg(theme.colors.fg())
            }
            BlockType::Code { .. } => {
                Style::default()
                    .fg(theme.colors.fg())
                    .bg(theme.colors.code_bg())
            }
            BlockType::InlineCode => {
                Style::default().fg(theme.colors.accent())
            }
            BlockType::ToolCall => {
                Style::default().fg(theme.colors.tool_call_col())
            }
            BlockType::ToolResult | BlockType::FileDiff => {
                Style::default().fg(theme.colors.tool_result_col())
            }
            BlockType::Thinking | BlockType::MemoryAccess => {
                Style::default().fg(theme.colors.thought()).add_modifier(Modifier::ITALIC)
            }
            BlockType::ModelSwitch | BlockType::PlanStep => {
                Style::default().fg(theme.colors.info_col()).add_modifier(Modifier::DIM)
            }
            BlockType::Warning => {
                Style::default().fg(theme.colors.warn())
            }
            BlockType::Error => {
                Style::default().fg(theme.colors.err()).add_modifier(Modifier::BOLD)
            }
        }
    }

    /// Get icon prefix for a block type.
    fn block_type_icon<'a>(block_type: &'a BlockType, theme: &'a Theme) -> &'a str {
        match block_type {
            BlockType::Prose | BlockType::System => "",
            BlockType::Code { .. } | BlockType::InlineCode => theme.icons.code.as_str(),
            BlockType::ToolCall => theme.icons.tool.as_str(),
            BlockType::ToolResult | BlockType::FileDiff => theme.icons.task_complete.as_str(),
            BlockType::Thinking | BlockType::MemoryAccess => theme.icons.thinking.as_str(),
            BlockType::ModelSwitch | BlockType::PlanStep => theme.icons.model.as_str(),
            BlockType::Warning => theme.icons.warning.as_str(),
            BlockType::Error => theme.icons.error.as_str(),
        }
    }

    /// Render a single message line with content-type-aware styling.
    fn render_message_line<'a>(msg: &'a crate::app::ChatMessage, theme: &'a Theme) -> Line<'a> {
        let content = &msg.content;
        let (icon, style) = match msg.kind {
            MessageKind::UserInput => (
                ">",
                Style::default().fg(theme.colors.accent()).add_modifier(Modifier::BOLD),
            ),
            MessageKind::AssistantResponse => (
                "",
                Style::default().fg(theme.colors.fg()),
            ),
            MessageKind::ToolCall => (
                theme.icons.tool.as_str(),
                Style::default().fg(theme.colors.tool_call_col()),
            ),
            MessageKind::ToolResult => (
                theme.icons.task_complete.as_str(),
                Style::default().fg(theme.colors.tool_result_col()),
            ),
            MessageKind::Thinking => (
                theme.icons.thinking.as_str(),
                Style::default().fg(theme.colors.thought()).add_modifier(Modifier::ITALIC),
            ),
            MessageKind::Error => (
                theme.icons.task_error.as_str(),
                Style::default().fg(theme.colors.err()).add_modifier(Modifier::BOLD),
            ),
            MessageKind::Warning => (
                theme.icons.warning.as_str(),
                Style::default().fg(theme.colors.warn()),
            ),
            MessageKind::System => (
                theme.icons.model.as_str(),
                Style::default().fg(theme.colors.info_col()).add_modifier(Modifier::DIM),
            ),
        };

        if icon.is_empty() {
            Line::from(Span::styled(content.clone(), style))
        } else {
            Line::from(Span::styled(format!(" {icon} {content}"), style))
        }
    }

    // ── Diff Pane (for developer layout) ───────────────────────────

    fn render_diff_pane(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let block = Block::default()
            .title(" Diff ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(area);

        let diff_lines: Vec<Line> = app.messages.iter()
            .filter(|m| m.kind == MessageKind::ToolResult || m.kind == MessageKind::ToolCall)
            .map(|m| {
                let is_success = m.kind == MessageKind::ToolResult;
                let icon = if is_success { &theme.icons.task_complete } else { &theme.icons.tool };
                let style = if is_success {
                    Style::default().fg(theme.colors.tool_result_col())
                } else {
                    Style::default().fg(theme.colors.tool_call_col())
                };
                let preview = if m.content.len() > 60 {
                    format!("{}...", &m.content[..60])
                } else {
                    m.content.clone()
                };
                Line::from(Span::styled(format!(" {icon} {preview}"), style))
            }).collect();

        frame.render_widget(
            Paragraph::new(if diff_lines.is_empty() {
                vec![Line::from(Span::styled(
                    " No changes yet ",
                    Style::default().fg(theme.colors.muted_col()).italic(),
                ))]
            } else {
                diff_lines
            }).block(block).wrap(Wrap { trim: false }),
            inner,
        );
    }

    // ── Memory Pane (for researcher layout) ────────────────────────

    fn render_memory_pane(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let block = Block::default()
            .title(" Memory ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(area);

        let msg_count = app.messages.len();
        let token_info = format!(" Tokens: {} in / {} out", Self::format_tokens(app.tokens_in), Self::format_tokens(app.tokens_out));
        let last_kind = app.messages.last().map(|m| format!("{:?}", m.kind)).unwrap_or_default();

        let lines = vec![
            Line::from(Span::styled(
                format!(" Messages: {msg_count}"),
                Style::default().fg(theme.colors.fg()),
            )),
            Line::from(Span::styled(
                token_info,
                Style::default().fg(theme.colors.muted_col()),
            )),
            Line::from(Span::styled(
                format!(" Last: {last_kind}"),
                Style::default().fg(theme.colors.info_col()).italic(),
            )),
            Line::from(Span::styled(
                format!(" Stream buf: {}B", app.stream_buffer.len()),
                Style::default().fg(theme.colors.muted_col()),
            )),
            Line::from(Span::styled(
                format!(" Model: {}", app.model_name),
                Style::default().fg(theme.colors.accent()),
            )),
            Line::from(Span::styled(
                format!(" Provider: {}", app.provider_name),
                Style::default().fg(theme.colors.accent2()),
            )),
        ];

        frame.render_widget(Paragraph::new(lines).block(block), inner);
    }

    // ── Agent Graph Pane (for orchestrator layout) ─────────────────

    fn render_agent_graph_pane(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
        let block = Block::default()
            .title(" Agent Graph ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(area);

        let lines = vec![
            Line::from(Span::styled(" ┌──────────────┐", theme.colors.accent())),
            Line::from(Span::styled(" │ Orchestrator  │", Style::default().fg(theme.colors.accent()).bold())),
            Line::from(Span::styled(" └──────┬───────┘", theme.colors.accent())),
            Line::from(Span::styled("    ┌───┼───┐", theme.colors.muted_col())),
            Line::from(Span::styled("    │   │   │", theme.colors.muted_col())),
            Line::from(vec![
                Span::styled(" ┌──┴──┐", theme.colors.accent2()),
                Span::styled(" ┌──┴──┐", theme.colors.accent2()),
                Span::styled(" ┌──┴──┐", theme.colors.accent2()),
            ]),
            Line::from(vec![
                Span::styled(" │Plan │", Style::default().fg(theme.colors.accent2()).bold()),
                Span::styled(" │Code │", Style::default().fg(theme.colors.accent2()).bold()),
                Span::styled(" │Review│", Style::default().fg(theme.colors.accent2()).bold()),
            ]),
            Line::from(vec![
                Span::styled(" └─────┘", theme.colors.accent2()),
                Span::styled(" └─────┘", theme.colors.accent2()),
                Span::styled(" └─────┘", theme.colors.accent2()),
            ]),
        ];

        frame.render_widget(Paragraph::new(lines).block(block), inner);
    }

    // ── Resource Monitor Pane (for monitor layout) ─────────────────

    fn render_resource_monitor(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let block = Block::default()
            .title(" Resources ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(area);

        let res = &app.resources;
        let bar_width = (inner.width as usize).saturating_sub(20).max(10);

        let cpu_bar = Self::progress_bar(res.cpu_usage as u8, bar_width);
        let cpu_pct = format!("{:.1}%", res.cpu_usage);
        let cpu_line = format!(" CPU: {cpu_bar} {cpu_pct}");
        let cpu_style = if res.cpu_usage > 90.0 {
            theme.colors.err()
        } else if res.cpu_usage > 70.0 {
            theme.colors.warn()
        } else {
            theme.colors.fg()
        };

        let mem_pct = if res.memory_total > 0 {
            (res.memory_used as f64 / res.memory_total as f64 * 100.0) as u8
        } else {
            0
        };
        let mem_bar = Self::progress_bar(mem_pct, bar_width);
        let mem_gb_used = res.memory_used as f64 / (1024.0 * 1024.0 * 1024.0);
        let mem_gb_total = res.memory_total as f64 / (1024.0 * 1024.0 * 1024.0);
        let mem_line = format!(" RAM: {mem_bar} {mem_gb_used:.1}/{mem_gb_total:.1}GB");
        let mem_style = if mem_pct > 90 {
            theme.colors.err()
        } else if mem_pct > 75 {
            theme.colors.warn()
        } else {
            theme.colors.fg()
        };

        let lines = vec![
            Line::from(Span::styled(cpu_line, cpu_style)),
            Line::from(Span::styled(mem_line, mem_style)),
            Line::from(Span::styled(
                format!(" Cores: {} | Procs: {} | {}", res.cpu_cores, res.process_count, res.host_name),
                Style::default().fg(theme.colors.muted_col()),
            )),
        ];

        frame.render_widget(Paragraph::new(lines).block(block), inner);
    }

    /// Render a text-based progress bar.
    fn progress_bar(pct: u8, width: usize) -> String {
        let filled = ((pct as usize * width).saturating_add(50)) / 100;
        let empty = width.saturating_sub(filled);
        format!(
            "[{}{}]",
            "█".repeat(filled.min(width)),
            "░".repeat(empty)
        )
    }

    // ── Analytics Pane (for monitor layout) ────────────────────────

    fn render_analytics_pane(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let block = Block::default()
            .title(" Analytics ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(area);

        let lines = vec![
            Line::from(format!(" Tokens in:  {}", Self::format_tokens(app.tokens_in))),
            Line::from(format!(" Tokens out: {}", Self::format_tokens(app.tokens_out))),
            Line::from(format!(" Messages:   {}", app.messages.len())),
            Line::from(format!(" Uptime:     {}", app.uptime_string())),
        ];

        frame.render_widget(Paragraph::new(lines).block(block), inner);
    }

    // ── Input Bar ─────────────────────────────────────────────────

    fn render_input_bar(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let border_style = if app.inspector_visible {
            theme.colors.muted_col()
        } else {
            theme.colors.accent()
        };

        let block = Block::default()
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .border_style(Style::default().fg(border_style));

        let inner = block.inner(area);

        let input_line = if app.phase == AppPhase::Processing {
            Line::from(Span::styled(
                " Agent is processing... (Ctrl+C to interrupt) ",
                Style::default().fg(theme.colors.muted_col()).italic(),
            ))
        } else {
            let mut spans = vec![];

            spans.push(Span::styled(
                &app.input_buffer[..app.input_cursor.min(app.input_buffer.len())],
                Style::default().fg(theme.colors.fg()),
            ));

            let cursor_char = if app.input_cursor < app.input_buffer.len() {
                &app.input_buffer[app.input_cursor..app.input_cursor + 1]
            } else {
                " "
            };
            spans.push(Span::styled(
                cursor_char,
                Style::default()
                    .bg(theme.colors.accent())
                    .fg(theme.colors.surface_col())
                    .add_modifier(Modifier::SLOW_BLINK),
            ));

            if app.input_cursor < app.input_buffer.len() {
                spans.push(Span::styled(
                    &app.input_buffer[app.input_cursor + 1..],
                    Style::default().fg(theme.colors.fg()),
                ));
            }

            if app.input_buffer.is_empty() {
                Line::from(Span::styled(
                    " Type a message... ",
                    Style::default().fg(theme.colors.muted_col()).italic(),
                ))
            } else {
                Line::from(spans)
            }
        };

        frame.render_widget(
            Paragraph::new(input_line).block(block).wrap(Wrap { trim: false }),
            area,
        );

        frame.set_cursor_position((inner.x + app.input_cursor as u16, inner.y));
    }

    // ── Full Task Inspector Overlay (uses inspector module) ────────

    fn render_full_inspector(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        // Full-screen inspector covering right 60% of the terminal
        let insp_w = (area.width as f64 * 0.6) as u16;
        let insp_area = Rect {
            x: area.width.saturating_sub(insp_w).max(20),
            y: 1,
            width: insp_w.min(area.width.saturating_sub(1)),
            height: area.height.saturating_sub(5).min(area.height),
        };

        inspector::render_inspector(frame, insp_area, app, theme);
    }

    // ── Memory Browser Overlay ───────────────────────────────────

    fn render_memory_browser(frame: &mut ratatui::Frame, area: Rect, app: &App, theme: &Theme) {
        let browser_w = area.width.saturating_sub(6).min(100);
        let browser_h = area.height.saturating_sub(4).min(30);
        let x = (area.width - browser_w) / 2;
        let y = (area.height - browser_h) / 3;
        let browser_area = Rect { x, y, width: browser_w, height: browser_h };

        let block = Block::default()
            .title(" Memory Browser [Ctrl+M] ")
            .borders(Borders::ALL)
            .border_type(Self::border_style(theme))
            .style(Style::default().bg(theme.colors.surface_col()));
        let inner = block.inner(browser_area);

        let (lines, scroll_state) = app.memory_browser.render(inner, theme);
        let paragraph = Paragraph::new(lines)
            .block(block)
            .wrap(Wrap { trim: false });

        frame.render_widget(paragraph, browser_area);

        let scrollbar = Scrollbar::new(ScrollbarOrientation::VerticalRight)
            .begin_symbol(Some("↑"))
            .end_symbol(Some("↓"));
        frame.render_stateful_widget(scrollbar, inner, &mut scroll_state.clone());
    }

    // ── Command Palette Overlay ────────────────────────────────────

    fn render_command_palette(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
        let palette_w = 50u16.min(area.width.saturating_sub(4));
        let palette_h = 17u16.min(area.height.saturating_sub(4));

        let palette_area = Rect {
            x: (area.width - palette_w) / 2,
            y: (area.height - palette_h) / 3,
            width: palette_w,
            height: palette_h,
        };

        let commands = vec![
            Line::from(Span::styled(
                " Command Palette ",
                Style::default().fg(theme.colors.accent()).bold(),
            )),
            Line::from(""),
            Line::from(Span::styled("  /help      Show help and available commands", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /quit      Exit session", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /clear     Clear chat history", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /status    Show agent status", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /model     Change active model", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /effort    Set effort level: low/medium/high/xhigh/max", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /fork      Branch current session", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /theme     Change theme", Style::default().fg(theme.colors.fg()))),
            Line::from(Span::styled("  /layout    Change layout: minimal/developer/researcher/orchestrator/monitor", Style::default().fg(theme.colors.fg()))),
            Line::from(""),
            Line::from(Span::styled("  Ctrl+P: Close  |  ↑↓: Navigate  |  Enter: Execute", Style::default().fg(theme.colors.muted_col()).dim())),
        ];

        let block = Block::default()
            .borders(Borders::ALL)
            .border_type(BorderType::Double)
            .style(Style::default().bg(theme.colors.surface_col()));

        frame.render_widget(
            Paragraph::new(commands).block(block),
            palette_area,
        );
    }

    // ── Interrupt Dialog Overlay ───────────────────────────────────

    fn render_interrupt_dialog(frame: &mut ratatui::Frame, area: Rect, _app: &App, theme: &Theme) {
        let dialog_width = 42u16.min(area.width.saturating_sub(4));
        let dialog_height = 8u16;

        let dialog_area = Rect {
            x: (area.width - dialog_width) / 2,
            y: (area.height - dialog_height) / 2,
            width: dialog_width,
            height: dialog_height,
        };

        let lines = vec![
            Line::from(Span::styled(
                " Agent Interrupted ",
                Style::default().fg(theme.colors.warn()).bold(),
            )),
            Line::from(""),
            Line::from(Span::styled(" What would you like to do?", Style::default().fg(theme.colors.fg()))),
            Line::from(""),
            Line::from(Span::styled("  [C] Cancel execution", Style::default().fg(theme.colors.err()))),
            Line::from(Span::styled("  [R] Redirect with new input", Style::default().fg(theme.colors.info_col()))),
            Line::from(Span::styled("  [Esc] Continue", Style::default().fg(theme.colors.muted_col()))),
        ];

        let block = Block::default()
            .borders(Borders::ALL)
            .border_type(BorderType::Double)
            .style(Style::default().bg(theme.colors.surface_col()));

        frame.render_widget(
            Paragraph::new(lines).block(block),
            dialog_area,
        );
    }

    // ── Helpers ────────────────────────────────────────────────────

    fn format_tokens(count: u64) -> String {
        if count >= 1_000_000 {
            format!("{:.1}M", count as f64 / 1_000_000.0)
        } else if count >= 1_000 {
            format!("{:.1}k", count as f64 / 1_000.0)
        } else {
            format!("{count}")
        }
    }

    fn border_style(theme: &Theme) -> BorderType {
        match theme.borders.style.as_str() {
            "sharp" => BorderType::Plain,
            "double" => BorderType::Double,
            "none" => BorderType::Plain,
            _ => BorderType::Rounded,
        }
    }
}

impl Drop for TuiEngine {
    fn drop(&mut self) {
        let _ = self.restore();
    }
}
