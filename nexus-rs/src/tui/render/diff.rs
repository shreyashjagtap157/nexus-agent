//! Diff engine — renders unified diffs for file write events.
//!
//! Parses unified diff output and produces styled line additions/removals
//! for inline display in the chat pane and task inspector diff panel.

use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};

use super::themes::Theme;

/// A single diff hunk with parsed lines.
#[derive(Debug, Clone)]
pub struct DiffHunk {
    /// File path being diffed.
    pub file_path: String,
    /// Parsed lines with their diff type.
    pub lines: Vec<DiffLine>,
    /// Total added lines count.
    pub added: usize,
    /// Total removed lines count.
    pub removed: usize,
}

/// A single line in a diff.
#[derive(Debug, Clone)]
pub struct DiffLine {
    /// The line content (without +/- prefix).
    pub content: String,
    /// Whether this is an addition, removal, or context.
    pub kind: DiffLineKind,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DiffLineKind {
    Addition,
    Removal,
    Context,
    Header,
}

/// Parse a unified diff string into structured hunks.
pub fn parse_diff(diff_text: &str) -> Vec<DiffHunk> {
    let mut hunks = Vec::new();
    let mut current_hunk: Option<DiffHunk> = None;

    for line in diff_text.lines() {
        if line.starts_with("---") || line.starts_with("+++") {
            // File header
            if let Some(hunk) = current_hunk.take() {
                hunks.push(hunk);
            }
            let path = line
                .trim_start_matches(['-', '+', '/', ' '])
                .trim()
                .to_string();
            current_hunk = Some(DiffHunk {
                file_path: path,
                lines: Vec::new(),
                added: 0,
                removed: 0,
            });
            if let Some(ref mut hunk) = current_hunk {
                hunk.lines.push(DiffLine {
                    content: line.to_string(),
                    kind: DiffLineKind::Header,
                });
            }
        } else if let Some(stripped) = line.strip_prefix('+') {
            if let Some(ref mut hunk) = current_hunk {
                hunk.added += 1;
                hunk.lines.push(DiffLine {
                    content: stripped.to_string(),
                    kind: DiffLineKind::Addition,
                });
            }
        } else if let Some(stripped) = line.strip_prefix('-') {
            if let Some(ref mut hunk) = current_hunk {
                hunk.removed += 1;
                hunk.lines.push(DiffLine {
                    content: stripped.to_string(),
                    kind: DiffLineKind::Removal,
                });
            }
        } else if line.starts_with("@@") {
            if let Some(ref mut hunk) = current_hunk {
                hunk.lines.push(DiffLine {
                    content: line.to_string(),
                    kind: DiffLineKind::Header,
                });
            }
        } else {
            if let Some(ref mut hunk) = current_hunk {
                hunk.lines.push(DiffLine {
                    content: line.to_string(),
                    kind: DiffLineKind::Context,
                });
            }
        }
    }

    if let Some(hunk) = current_hunk {
        hunks.push(hunk);
    }

    hunks
}

/// Render a diff hunk as styled Ratatui Lines.
pub fn render_diff<'a>(hunk: &'a DiffHunk, theme: &'a Theme) -> Vec<Line<'a>> {
    let mut lines = Vec::new();

    // File header
    lines.push(Line::from(Span::styled(
        format!(" {} {} ", theme.icons.file, hunk.file_path),
        Style::default()
            .fg(theme.colors.accent())
            .add_modifier(Modifier::BOLD),
    )));

        // Summary
        let summary = if hunk.added > 0 && hunk.removed > 0 {
            format!("+{}/-{}", hunk.added, hunk.removed)
        } else if hunk.added > 0 {
            format!("+{}", hunk.added)
        } else if hunk.removed > 0 {
            format!("-{}", hunk.removed)
        } else {
            String::new()
        };
        lines.push(Line::from(Span::styled(
            format!("   {} {}", summary, theme.icons.tool),
            Style::default().fg(theme.colors.muted_col()),
        )));

    lines.push(Line::from(""));

    // Diff lines
    for diff_line in &hunk.lines {
        let (style, prefix) = match diff_line.kind {
            DiffLineKind::Addition => (
                Style::default().fg(theme.colors.diff_add_col()),
                "+",
            ),
            DiffLineKind::Removal => (
                Style::default().fg(theme.colors.diff_remove_col()),
                "-",
            ),
            DiffLineKind::Header => (
                Style::default()
                    .fg(theme.colors.muted_col())
                    .add_modifier(Modifier::DIM),
                "",
            ),
            DiffLineKind::Context => (
                Style::default().fg(theme.colors.fg()),
                " ",
            ),
        };

        lines.push(Line::from(Span::styled(
            format!("{}{}", prefix, diff_line.content),
            style,
        )));
    }

    lines
}
