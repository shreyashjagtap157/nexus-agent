//! TUI module — Ratatui terminal UI components.
//!
//! The TUI engine manages the crossterm raw-mode render loop, keyboard
//! input, and frame compositing. Sub-components handle individual panes.

pub mod engine;
pub mod inspector;
pub mod memory_browser;
pub mod render;
