//! Render pipeline — streaming render engine with block detection,
//! content-type formatting, theme system, diff engine, and multi-pane compositor.
//!
//! Pipeline stages:
//! 1. BlockDetector — accumulate tokens, classify content type
//! 2. ThemeEngine — apply active theme colors/icons/borders
//! 3. DiffEngine — parse and style unified diffs
//! 4. LayoutCompositor — arrange panes per preset
//! 5. Formatter — produce styled Ratatui widgets per content type

pub mod blocks;
pub mod compositor;
pub mod diff;
pub mod themes;
