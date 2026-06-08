//! Config loader — discovers, reads, and merges configuration from
//! multiple sources with proper precedence.

use std::path::PathBuf;
use tracing::warn;

use super::types::Config;

/// Load the configuration from the file system, merging sources in order
/// of increasing precedence.
///
/// Precedence (low → high):
/// 1. Default values
/// 2. User config (~/.config/nexus/config.toml or %APPDATA%/nexus/config.toml)
/// 3. Project-local config (./.nexus/config.toml)
/// 4. `$NEXUS_CONFIG` env var
/// 5. CLI argument overrides (applied by caller via `with_cli_overrides`)
pub fn load_config() -> Config {
    let mut config = Config::default();

    // 1. User global config
    if let Some(user_path) = user_config_path() {
        if user_path.exists() {
            match merge_toml_file(&user_path, &mut config) {
                Ok(()) => tracing::debug!("Loaded user config from {:?}", user_path),
                Err(e) => warn!("Failed to parse user config {:?}: {e}", user_path),
            }
        }
    }

    // 2. Project-local config
    if let Ok(cwd) = std::env::current_dir() {
        let local_path = cwd.join(".nexus").join("config.toml");
        if local_path.exists() {
            match merge_toml_file(&local_path, &mut config) {
                Ok(()) => tracing::debug!("Loaded project config from {:?}", local_path),
                Err(e) => warn!("Failed to parse project config {:?}: {e}", local_path),
            }
        }
    }

    // 3. NEXUS_CONFIG env var
    if let Ok(env_path) = std::env::var("NEXUS_CONFIG") {
        let env_path = PathBuf::from(env_path);
        if env_path.exists() {
            match merge_toml_file(&env_path, &mut config) {
                Ok(()) => tracing::debug!("Loaded env config from {:?}", env_path),
                Err(e) => warn!("Failed to parse env config {:?}: {e}", env_path),
            }
        }
    }

    config
}

/// Merge a TOML file on top of the current config.
/// Fields in the file override those in the base config.
fn merge_toml_file(path: &std::path::Path, config: &mut Config) -> Result<(), Box<dyn std::error::Error>> {
    let content = std::fs::read_to_string(path)?;
    let file_config: Config = toml::from_str(&content)?;

    // Merge optional fields
    if file_config.model.is_some() {
        config.model = file_config.model;
    }
    if let Some(w) = file_config.workspace {
        config.workspace = Some(w);
    }
    if !file_config.keybindings.is_empty() {
        config.keybindings = file_config.keybindings;
    }

    // Merge simple fields (overwrite if set)
    // We can't easily check "was this field set in the file" for non-optional
    // fields in toml. For now, we overwrite. This means the DEFAULT values
    // in Config::default() will be overwritten by ANY value in the file,
    // which is the expected behavior.
    // Only override non-default-ish fields
    // For provider/theme/layout, we rely on the file being parsed as a whole
    // and merging top-level fields.
    config.provider = file_config.provider;
    config.theme = file_config.theme;
    config.layout = file_config.layout;
    config.agent = file_config.agent;

    if file_config.theme_colors.is_some() {
        config.theme_colors = file_config.theme_colors;
    }

    Ok(())
}

/// Get the user-level config directory path.
fn user_config_path() -> Option<PathBuf> {
    // Try XDG/config dir first (cross-platform via directories crate)
    if let Some(proj_dirs) = directories::ProjectDirs::from("dev", "nexus-agent", "nexus") {
        let config_dir = proj_dirs.config_dir().to_path_buf();
        return Some(config_dir.join("config.toml"));
    }

    // Fallback: manual path resolution
    #[cfg(target_os = "linux")]
    {
        if let Ok(xdg) = std::env::var("XDG_CONFIG_HOME") {
            return Some(PathBuf::from(xdg).join("nexus/config.toml"));
        }
        if let Ok(home) = std::env::var("HOME") {
            return Some(PathBuf::from(home).join(".config/nexus/config.toml"));
        }
    }
    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            return Some(
                PathBuf::from(home).join("Library/Application Support/nexus/config.toml"),
            );
        }
    }
    #[cfg(target_os = "windows")]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            return Some(PathBuf::from(appdata).join("nexus/config.toml"));
        }
    }

    None
}
