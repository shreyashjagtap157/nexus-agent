//! Memory Browser TUI — explorable tree of all 5 memory tiers.
//!
//! Ctrl+M toggles the overlay. Shows memory entries from working,
//! long-term, episodic, vector stores and user profile with
//! search/filter by tier and pagination support.

use ratatui::layout::Rect;
use ratatui::style::{Modifier, Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::ScrollbarState;

/// Memory tier identifiers matching the Python backend.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MemoryTier {
    Working,
    LongTerm,
    Episodic,
    VectorStore,
    UserProfile,
}

impl MemoryTier {
    pub const ALL: &'static [MemoryTier] = &[
        Self::Working,
        Self::LongTerm,
        Self::Episodic,
        Self::VectorStore,
        Self::UserProfile,
    ];

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Working => "Working",
            Self::LongTerm => "Long-Term",
            Self::Episodic => "Episodic",
            Self::VectorStore => "Vector",
            Self::UserProfile => "Profile",
        }
    }
}

/// A single memory entry as displayed in the browser.
#[derive(Debug, Clone)]
pub struct MemoryEntry {
    pub id: String,
    pub content: String,
    pub tier: MemoryTier,
    pub category: String,
    pub created_at: f64,
    pub updated_at: f64,
    pub access_count: usize,
    pub score: f64,
}

/// State of the memory browser overlay.
#[derive(Debug, Clone)]
pub struct MemoryBrowser {
    /// Whether the browser is visible.
    pub visible: bool,
    /// Currently selected tier filter (None = all).
    pub selected_tier: Option<MemoryTier>,
    /// Cached entries from backend.
    pub entries: Vec<MemoryEntry>,
    /// Search query string.
    pub search_query: String,
    /// Scroll offset.
    pub scroll: usize,
    /// Total entries available.
    pub total_count: usize,
    /// Whether we're in search mode.
    pub search_mode: bool,
    /// Counts per tier (populated by stats).
    pub tier_counts: Vec<(MemoryTier, usize)>,
    /// Last error message.
    pub error: Option<String>,
}

impl Default for MemoryBrowser {
    fn default() -> Self {
        Self {
            visible: false,
            selected_tier: None,
            entries: Vec::new(),
            search_query: String::new(),
            scroll: 0,
            total_count: 0,
            search_mode: false,
            tier_counts: MemoryTier::ALL.iter().map(|t| (*t, 0)).collect(),
            error: None,
        }
    }
}

impl MemoryBrowser {
    /// Set entries from an ACP response.
    pub fn set_entries(&mut self, entries: Vec<MemoryEntry>, total: usize) {
        self.entries = entries;
        self.total_count = total;
        self.scroll = 0;
        self.error = None;
    }

    /// Set an error message.
    pub fn set_error(&mut self, err: String) {
        self.error = Some(err);
        self.entries.clear();
    }

    /// Get entries matching the current tier filter.
    pub fn filtered_entries(&self) -> Vec<&MemoryEntry> {
        match self.selected_tier {
            Some(tier) => self.entries.iter().filter(|e| e.tier == tier).collect(),
            None => self.entries.iter().collect(),
        }
    }

    /// Render the memory browser as lines for the overlay.
    pub fn render(&self, area: Rect, theme: &super::render::themes::Theme) -> (Vec<Line<'_>>, ScrollbarState) {
        let mut lines: Vec<Line> = Vec::new();

        // Header: tier selector
        let mut header_spans = vec![
            Span::styled(" Tiers: ", Style::default().fg(theme.colors.muted_col())),
        ];
        for (tier, &(_, count)) in MemoryTier::ALL.iter().zip(self.tier_counts.iter()) {
            let is_selected = self.selected_tier == Some(*tier);
            let style = if is_selected {
                Style::default().fg(theme.colors.accent()).add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.colors.fg())
            };
            let name = if count > 0 {
                format!(" {}:{} ", tier.as_str(), count)
            } else {
                format!(" {} ", tier.as_str())
            };
            header_spans.push(Span::styled(name, style));
            header_spans.push(Span::styled("│", Style::default().fg(theme.colors.muted_col())));
        }
        header_spans.push(Span::styled(
            if self.search_mode { " [Search]" } else { " [/search]" },
            Style::default().fg(theme.colors.info_col()).italic(),
        ));
        lines.push(Line::from(header_spans));
        lines.push(Line::from(Span::styled(
            "─".repeat(area.width.saturating_sub(2) as usize),
            Style::default().fg(theme.colors.muted_col()),
        )));

        // Search bar
        if self.search_mode {
            lines.push(Line::from(Span::styled(
                format!(" Search: {}█", self.search_query),
                Style::default().fg(theme.colors.accent()),
            )));
            lines.push(Line::from(Span::styled(
                "─".repeat(area.width.saturating_sub(2) as usize),
                Style::default().fg(theme.colors.muted_col()),
            )));
        }

        // Error message
        if let Some(ref err) = self.error {
            lines.push(Line::from(Span::styled(
                format!(" ✗ {err}"),
                Style::default().fg(theme.colors.err()),
            )));
            return (lines, ScrollbarState::new(0));
        }

        // Entry list
        let filtered = self.filtered_entries();
        if filtered.is_empty() {
            lines.push(Line::from(Span::styled(
                if self.search_query.is_empty() {
                    " No memories found "
                } else {
                    " No matching memories "
                },
                Style::default().fg(theme.colors.muted_col()).italic(),
            )));
        } else {
            let max_content = (area.width.saturating_sub(6) as usize).min(80);
            for entry in filtered.iter().skip(self.scroll).take(area.height.saturating_sub(6) as usize) {
                let tier_style = match entry.tier {
                    MemoryTier::Working => theme.colors.accent(),
                    MemoryTier::LongTerm => theme.colors.ok(),
                    MemoryTier::Episodic => theme.colors.info_col(),
                    MemoryTier::VectorStore => theme.colors.accent2(),
                    MemoryTier::UserProfile => theme.colors.warn(),
                };
                let icon = match entry.tier {
                    MemoryTier::Working => "W",
                    MemoryTier::LongTerm => "L",
                    MemoryTier::Episodic => "E",
                    MemoryTier::VectorStore => "V",
                    MemoryTier::UserProfile => "P",
                };
                let preview = if entry.content.len() > max_content {
                    format!("{}...", &entry.content[..max_content])
                } else {
                    entry.content.clone()
                };
                let score_str = if entry.score > 0.0 {
                    format!(" {:.2}", entry.score)
                } else {
                    String::new()
                };
                lines.push(Line::from(vec![
                    Span::styled(format!(" {icon} "), Style::default().fg(tier_style).bold()),
                    Span::styled(preview, Style::default().fg(theme.colors.fg())),
                    Span::styled(score_str, Style::default().fg(theme.colors.muted_col())),
                ]));
            }
        }

        // Footer with entry count
        lines.push(Line::from(Span::styled(
            format!(" {} entries shown / {} total ", filtered.len(), self.total_count),
            Style::default().fg(theme.colors.muted_col()).italic(),
        )));

        let max_scroll = filtered.len().saturating_sub(area.height.saturating_sub(6) as usize);
        let state = ScrollbarState::new(max_scroll).position(self.scroll.min(max_scroll));
        (lines, state)
    }
}
