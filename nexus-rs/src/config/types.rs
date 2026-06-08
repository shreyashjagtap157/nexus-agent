//! Configuration type definitions.

use serde::Deserialize;

/// Top-level configuration for the Nexus CLI.
#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    /// Default model path or alias.
    #[serde(default)]
    pub model: Option<String>,

    /// Default provider (local, anthropic, openai, etc.).
    #[serde(default = "default_provider")]
    pub provider: String,

    /// Workspace directory (defaults to current directory).
    #[serde(default)]
    pub workspace: Option<String>,

    /// Active theme name.
    #[serde(default = "default_theme")]
    pub theme: String,

    /// Active layout preset name.
    #[serde(default = "default_layout")]
    pub layout: String,

    /// Custom keybinding overrides.
    #[serde(default)]
    pub keybindings: Vec<Keybinding>,

    /// Agent-specific settings.
    #[serde(default)]
    pub agent: AgentConfig,

    /// Theme color overrides (optional).
    #[serde(default)]
    pub theme_colors: Option<ThemeColors>,
}

/// Agent-specific configuration.
#[derive(Debug, Clone, Deserialize)]
pub struct AgentConfig {
    /// Effort level (low/medium/high/xhigh/max).
    #[serde(default = "default_effort")]
    pub effort: String,

    /// Permission mode (auto/ask/suggest).
    #[serde(default = "default_permission")]
    pub permission: String,
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            effort: default_effort(),
            permission: default_permission(),
        }
    }
}

/// Theme colors — hex strings like "#1a1b26".
#[derive(Debug, Clone, Deserialize)]
pub struct ThemeColors {
    #[serde(default)]
    pub background: Option<String>,
    #[serde(default)]
    pub foreground: Option<String>,
    #[serde(default)]
    pub accent: Option<String>,
    #[serde(default)]
    pub success: Option<String>,
    #[serde(default)]
    pub warning: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub muted: Option<String>,
    #[serde(default)]
    pub surface: Option<String>,
}

/// A custom keybinding override.
#[derive(Debug, Clone, Deserialize)]
pub struct Keybinding {
    /// Action name (e.g., "toggle_inspector", "open_palette").
    pub action: String,
    /// Key sequence (e.g., "ctrl-t", "page-up", "f5").
    pub key: String,
}

// ── Defaults ─────────────────────────────────────────────────────────

fn default_provider() -> String {
    "local".to_string()
}

fn default_theme() -> String {
    "dark".to_string()
}

fn default_layout() -> String {
    "minimal".to_string()
}

fn default_effort() -> String {
    "medium".to_string()
}

fn default_permission() -> String {
    "suggest".to_string()
}

impl Default for Config {
    fn default() -> Self {
        Self {
            model: None,
            provider: default_provider(),
            workspace: None,
            theme: default_theme(),
            layout: default_layout(),
            keybindings: Vec::new(),
            agent: AgentConfig::default(),
            theme_colors: None,
        }
    }
}

impl Config {
    /// Merge CLI overrides on top of the loaded config.
    /// CLI args take highest precedence.
    pub fn with_cli_overrides(
        mut self,
        cli_model: Option<String>,
        cli_provider: Option<String>,
        cli_workspace: Option<String>,
    ) -> Self {
        if let Some(m) = cli_model {
            self.model = Some(m);
        }
        if let Some(p) = cli_provider {
            self.provider = p;
        }
        if let Some(w) = cli_workspace {
            self.workspace = Some(w);
        }
        self
    }
}
