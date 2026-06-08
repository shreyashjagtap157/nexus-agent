//! Visual theme system — TOML-defined, hot-reloadable color/icon/border presets.
//!
//! Every color, icon glyph, border style, and animation speed is a theme variable.
//! Themes are user-extensible: drop a TOML file into `~/.config/nexus/themes/`.

use ratatui::style::Color;
use serde::Deserialize;
use std::collections::HashMap;
use std::path::PathBuf;

// ── Theme Data ─────────────────────────────────────────────────────────

/// Full theme definition — colors, icons, borders, and metadata.
#[derive(Debug, Clone, Deserialize)]
pub struct Theme {
    /// Display name.
    pub name: String,
    /// Semantic color palette.
    pub colors: ThemeColors,
    /// Content-type icon glyphs.
    #[serde(default)]
    pub icons: ThemeIcons,
    /// Border styles.
    #[serde(default)]
    pub borders: ThemeBorders,
    /// Whether this is a dark theme (affects some rendering choices).
    #[serde(default = "default_dark")]
    pub dark: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ThemeColors {
    #[serde(default = "c_default")]
    pub background: String,
    #[serde(default = "c_foreground")]
    pub foreground: String,
    #[serde(default = "c_accent_primary")]
    pub accent_primary: String,
    #[serde(default = "c_accent_secondary")]
    pub accent_secondary: String,
    #[serde(default = "c_success")]
    pub success: String,
    #[serde(default = "c_warning")]
    pub warning: String,
    #[serde(default = "c_error")]
    pub error: String,
    #[serde(default = "c_info")]
    pub info: String,
    #[serde(default = "c_muted")]
    pub muted: String,
    #[serde(default = "c_surface")]
    pub surface: String,
    #[serde(default = "c_agent_thought")]
    pub agent_thought: String,
    #[serde(default = "c_tool_call")]
    pub tool_call: String,
    #[serde(default = "c_tool_result")]
    pub tool_result: String,
    #[serde(default = "c_code_bg")]
    pub code_bg: String,
    #[serde(default = "c_diff_add")]
    pub diff_add: String,
    #[serde(default = "c_diff_remove")]
    pub diff_remove: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ThemeIcons {
    #[serde(default = "i_agent")]
    pub agent: String,
    #[serde(default = "i_tool")]
    pub tool: String,
    #[serde(default = "i_memory")]
    pub memory: String,
    #[serde(default = "i_model")]
    pub model: String,
    #[serde(default = "i_task_running")]
    pub task_running: String,
    #[serde(default = "i_task_complete")]
    pub task_complete: String,
    #[serde(default = "i_task_error")]
    pub task_error: String,
    #[serde(default = "i_thinking")]
    pub thinking: String,
    #[serde(default = "i_warning")]
    pub warning: String,
    #[serde(default = "i_error")]
    pub error: String,
    #[serde(default = "i_file")]
    pub file: String,
    #[serde(default = "i_folder")]
    pub folder: String,
    #[serde(default = "i_code")]
    pub code: String,
}

impl Default for ThemeIcons {
    fn default() -> Self {
        Self {
            agent: i_agent(),
            tool: i_tool(),
            memory: i_memory(),
            model: i_model(),
            task_running: i_task_running(),
            task_complete: i_task_complete(),
            task_error: i_task_error(),
            thinking: i_thinking(),
            warning: i_warning(),
            error: i_error(),
            file: i_file(),
            folder: i_folder(),
            code: i_code(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct ThemeBorders {
    #[serde(default = "b_style")]
    pub style: String,
}

impl Default for ThemeBorders {
    fn default() -> Self {
        Self { style: b_style() }
    }
}

impl Default for Theme {
    fn default() -> Self {
        Self {
            name: "dark".into(),
            colors: ThemeColors::default(),
            icons: ThemeIcons::default(),
            borders: ThemeBorders::default(),
            dark: true,
        }
    }
}

impl ThemeColors {
    pub fn bg(&self) -> Color { hex(&self.background) }
    pub fn fg(&self) -> Color { hex(&self.foreground) }
    pub fn accent(&self) -> Color { hex(&self.accent_primary) }
    pub fn accent2(&self) -> Color { hex(&self.accent_secondary) }
    pub fn ok(&self) -> Color { hex(&self.success) }
    pub fn warn(&self) -> Color { hex(&self.warning) }
    pub fn err(&self) -> Color { hex(&self.error) }
    pub fn info_col(&self) -> Color { hex(&self.info) }
    pub fn muted_col(&self) -> Color { hex(&self.muted) }
    pub fn surface_col(&self) -> Color { hex(&self.surface) }
    pub fn thought(&self) -> Color { hex(&self.agent_thought) }
    pub fn tool_call_col(&self) -> Color { hex(&self.tool_call) }
    pub fn tool_result_col(&self) -> Color { hex(&self.tool_result) }
    pub fn code_bg(&self) -> Color { hex(&self.code_bg) }
    pub fn diff_add_col(&self) -> Color { hex(&self.diff_add) }
    pub fn diff_remove_col(&self) -> Color { hex(&self.diff_remove) }
}

impl Default for ThemeColors {
    fn default() -> Self {
        Self {
            background: c_default(),
            foreground: c_foreground(),
            accent_primary: c_accent_primary(),
            accent_secondary: c_accent_secondary(),
            success: c_success(),
            warning: c_warning(),
            error: c_error(),
            info: c_info(),
            muted: c_muted(),
            surface: c_surface(),
            agent_thought: c_agent_thought(),
            tool_call: c_tool_call(),
            tool_result: c_tool_result(),
            code_bg: c_code_bg(),
            diff_add: c_diff_add(),
            diff_remove: c_diff_remove(),
        }
    }
}

// ── Built-in Theme Presets ─────────────────────────────────────────────

/// All built-in themes. Indexed by name.
pub fn builtin_themes() -> HashMap<String, Theme> {
    let mut map = HashMap::new();
    map.insert("dark".into(), dark_theme());
    map.insert("light".into(), light_theme());
    map.insert("catppuccin-mocha".into(), catppuccin_mocha());
    map.insert("tokyo-night".into(), tokyo_night());
    map.insert("gruvbox".into(), gruvbox());
    map.insert("nord".into(), nord());
    map.insert("high-contrast".into(), high_contrast());
    map.insert("minimal".into(), minimal());
    map
}

fn dark_theme() -> Theme {
    Theme {
        name: "dark".into(),
        colors: ThemeColors {
            background: "#1a1b26".into(), foreground: "#c0caf5".into(),
            accent_primary: "#7aa2f7".into(), accent_secondary: "#bb9af7".into(),
            success: "#9ece6a".into(), warning: "#e0af68".into(), error: "#f7768e".into(),
            info: "#7dcfff".into(), muted: "#565f89".into(), surface: "#24283b".into(),
            agent_thought: "#414868".into(), tool_call: "#2ac3de".into(), tool_result: "#73daca".into(),
            code_bg: "#1f2335".into(), diff_add: "#9ece6a".into(), diff_remove: "#f7768e".into(),
        },
        dark: true, ..Default::default()
    }
}

fn light_theme() -> Theme {
    Theme {
        name: "light".into(),
        colors: ThemeColors {
            background: "#f4f4f9".into(), foreground: "#1a1a2e".into(),
            accent_primary: "#4361ee".into(), accent_secondary: "#7209b7".into(),
            success: "#2d6a4f".into(), warning: "#e85d04".into(), error: "#d00000".into(),
            info: "#00b4d8".into(), muted: "#8d99ae".into(), surface: "#e8e8ed".into(),
            agent_thought: "#c0c0cc".into(), tool_call: "#0077b6".into(), tool_result: "#2d6a4f".into(),
            code_bg: "#e0e0e8".into(), diff_add: "#2d6a4f".into(), diff_remove: "#d00000".into(),
        },
        dark: false, ..Default::default()
    }
}

fn catppuccin_mocha() -> Theme {
    Theme {
        name: "catppuccin-mocha".into(),
        colors: ThemeColors {
            background: "#1e1e2e".into(), foreground: "#cdd6f4".into(),
            accent_primary: "#89b4fa".into(), accent_secondary: "#cba6f7".into(),
            success: "#a6e3a1".into(), warning: "#fab387".into(), error: "#f38ba8".into(),
            info: "#89dceb".into(), muted: "#585b70".into(), surface: "#313244".into(),
            agent_thought: "#45475a".into(), tool_call: "#74c7ec".into(), tool_result: "#a6e3a1".into(),
            code_bg: "#181825".into(), diff_add: "#a6e3a1".into(), diff_remove: "#f38ba8".into(),
        },
        dark: true, ..Default::default()
    }
}

fn tokyo_night() -> Theme {
    Theme {
        name: "tokyo-night".into(),
        colors: ThemeColors {
            background: "#1a1b26".into(), foreground: "#c0caf5".into(),
            accent_primary: "#7aa2f7".into(), accent_secondary: "#bb9af7".into(),
            success: "#9ece6a".into(), warning: "#e0af68".into(), error: "#f7768e".into(),
            info: "#7dcfff".into(), muted: "#565f89".into(), surface: "#24283b".into(),
            agent_thought: "#414868".into(), tool_call: "#2ac3de".into(), tool_result: "#73daca".into(),
            code_bg: "#1f2335".into(), diff_add: "#9ece6a".into(), diff_remove: "#f7768e".into(),
        },
        dark: true, ..Default::default()
    }
}

fn gruvbox() -> Theme {
    Theme {
        name: "gruvbox".into(),
        colors: ThemeColors {
            background: "#282828".into(), foreground: "#ebdbb2".into(),
            accent_primary: "#83a598".into(), accent_secondary: "#d3869b".into(),
            success: "#b8bb26".into(), warning: "#fe8019".into(), error: "#fb4934".into(),
            info: "#8ec07c".into(), muted: "#928374".into(), surface: "#3c3836".into(),
            agent_thought: "#504945".into(), tool_call: "#83a598".into(), tool_result: "#b8bb26".into(),
            code_bg: "#1d2021".into(), diff_add: "#b8bb26".into(), diff_remove: "#fb4934".into(),
        },
        dark: true, ..Default::default()
    }
}

fn nord() -> Theme {
    Theme {
        name: "nord".into(),
        colors: ThemeColors {
            background: "#2e3440".into(), foreground: "#d8dee9".into(),
            accent_primary: "#81a1c1".into(), accent_secondary: "#b48ead".into(),
            success: "#a3be8c".into(), warning: "#d08770".into(), error: "#bf616a".into(),
            info: "#88c0d0".into(), muted: "#4c566a".into(), surface: "#3b4252".into(),
            agent_thought: "#434c5e".into(), tool_call: "#81a1c1".into(), tool_result: "#a3be8c".into(),
            code_bg: "#242933".into(), diff_add: "#a3be8c".into(), diff_remove: "#bf616a".into(),
        },
        dark: true, ..Default::default()
    }
}

fn high_contrast() -> Theme {
    Theme {
        name: "high-contrast".into(),
        colors: ThemeColors {
            background: "#000000".into(), foreground: "#ffffff".into(),
            accent_primary: "#ffff00".into(), accent_secondary: "#00ffff".into(),
            success: "#00ff00".into(), warning: "#ffaa00".into(), error: "#ff0000".into(),
            info: "#00ffff".into(), muted: "#aaaaaa".into(), surface: "#222222".into(),
            agent_thought: "#555555".into(), tool_call: "#00ffff".into(), tool_result: "#00ff00".into(),
            code_bg: "#111111".into(), diff_add: "#00ff00".into(), diff_remove: "#ff0000".into(),
        },
        dark: true, ..Default::default()
    }
}

fn minimal() -> Theme {
    Theme {
        name: "minimal".into(),
        colors: ThemeColors {
            background: "#111111".into(), foreground: "#cccccc".into(),
            accent_primary: "#888888".into(), accent_secondary: "#aaaaaa".into(),
            success: "#888888".into(), warning: "#aaaaaa".into(), error: "#cc6666".into(),
            info: "#999999".into(), muted: "#555555".into(), surface: "#1a1a1a".into(),
            agent_thought: "#333333".into(), tool_call: "#999999".into(), tool_result: "#aaaaaa".into(),
            code_bg: "#0d0d0d".into(), diff_add: "#888888".into(), diff_remove: "#cc6666".into(),
        },
        dark: true, ..Default::default()
    }
}

// ── Loader ─────────────────────────────────────────────────────────────

/// Load a named theme: checks user themes dir first, then built-in presets.
pub fn load_theme(name: &str, user_theme_dir: Option<&PathBuf>) -> Theme {
    // Try user-provided theme files
    if let Some(dir) = user_theme_dir {
        let path = dir.join(format!("{name}.toml"));
        if path.exists() {
            if let Ok(content) = std::fs::read_to_string(&path) {
                if let Ok(theme) = toml::from_str::<Theme>(&content) {
                    return theme;
                }
            }
        }
    }

    // Try built-in presets
    let builtins = builtin_themes();
    if let Some(theme) = builtins.get(name) {
        return theme.clone();
    }

    // Fallback to dark
    dark_theme()
}

// ── Color Parsing ──────────────────────────────────────────────────────

/// Parse a hex color string to Ratatui Color.
pub fn hex(s: &str) -> Color {
    let s = s.trim_start_matches('#');
    if s.len() == 6 {
        if let Ok(r) = u8::from_str_radix(&s[0..2], 16) {
            if let Ok(g) = u8::from_str_radix(&s[2..4], 16) {
                if let Ok(b) = u8::from_str_radix(&s[4..6], 16) {
                    return Color::Rgb(r, g, b);
                }
            }
        }
    }
    Color::Reset
}

// ── Default Value Functions ────────────────────────────────────────────

fn default_dark() -> bool { true }
fn c_default() -> String { "#1a1b26".into() }
fn c_foreground() -> String { "#c0caf5".into() }
fn c_accent_primary() -> String { "#7aa2f7".into() }
fn c_accent_secondary() -> String { "#bb9af7".into() }
fn c_success() -> String { "#9ece6a".into() }
fn c_warning() -> String { "#e0af68".into() }
fn c_error() -> String { "#f7768e".into() }
fn c_info() -> String { "#7dcfff".into() }
fn c_muted() -> String { "#565f89".into() }
fn c_surface() -> String { "#24283b".into() }
fn c_agent_thought() -> String { "#414868".into() }
fn c_tool_call() -> String { "#2ac3de".into() }
fn c_tool_result() -> String { "#73daca".into() }
fn c_code_bg() -> String { "#1f2335".into() }
fn c_diff_add() -> String { "#9ece6a".into() }
fn c_diff_remove() -> String { "#f7768e".into() }

fn i_agent() -> String { "◈".into() }
fn i_tool() -> String { "⚙".into() }
fn i_memory() -> String { "◦".into() }
fn i_model() -> String { "◉".into() }
fn i_task_running() -> String { "▶".into() }
fn i_task_complete() -> String { "✓".into() }
fn i_task_error() -> String { "✗".into() }
fn i_thinking() -> String { "⋯".into() }
fn i_warning() -> String { "⚠".into() }
fn i_error() -> String { "✗".into() }
fn i_file() -> String { "📄".into() }
fn i_folder() -> String { "📁".into() }
fn i_code() -> String { "</>".into() }

fn b_style() -> String { "rounded".into() }
