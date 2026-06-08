//! Configuration module — load/save/validate Nexus config.
//!
//! Config is loaded from TOML files with the following precedence:
//! 1. `$NEXUS_CONFIG` env var
//! 2. `./.nexus/config.toml` (project-local)
//! 3. `~/.config/nexus/config.toml` (user global)
//! 4. Default values

pub mod loader;
pub mod types;
