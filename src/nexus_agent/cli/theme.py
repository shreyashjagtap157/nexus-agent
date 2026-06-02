"""
CLI Theme — Color definitions for the TUI interface.

Defines a premium dark theme with vibrant accent colors
inspired by modern coding agent interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThemeColors:
    """Color palette for the TUI."""
    # Background
    bg_primary: str = "#0d1117"
    bg_secondary: str = "#161b22"
    bg_tertiary: str = "#1c2333"
    bg_surface: str = "#21262d"
    bg_hover: str = "#30363d"

    # Text
    text_primary: str = "#e6edf3"
    text_secondary: str = "#8b949e"
    text_muted: str = "#484f58"
    text_accent: str = "#58a6ff"

    # Accent colors
    accent_primary: str = "#58a6ff"    # Blue
    accent_secondary: str = "#bc8cff"  # Purple
    accent_success: str = "#3fb950"    # Green
    accent_warning: str = "#d29922"    # Yellow/Gold
    accent_error: str = "#f85149"      # Red
    accent_info: str = "#79c0ff"       # Light blue

    # Agent states
    state_thinking: str = "#d2a8ff"    # Soft purple
    state_executing: str = "#58a6ff"   # Blue
    state_done: str = "#3fb950"        # Green
    state_error: str = "#f85149"       # Red

    # Borders
    border_default: str = "#30363d"
    border_active: str = "#58a6ff"
    border_focus: str = "#bc8cff"

    # Syntax highlighting
    syntax_keyword: str = "#ff7b72"
    syntax_string: str = "#a5d6ff"
    syntax_comment: str = "#8b949e"
    syntax_function: str = "#d2a8ff"
    syntax_number: str = "#79c0ff"
    syntax_operator: str = "#ff7b72"


# Default theme instance
DARK_THEME = ThemeColors()

# Light theme (for future use)
LIGHT_THEME = ThemeColors(
    bg_primary="#ffffff",
    bg_secondary="#f6f8fa",
    bg_tertiary="#f0f3f6",
    bg_surface="#e8ecf0",
    bg_hover="#d0d7de",
    text_primary="#1f2328",
    text_secondary="#656d76",
    text_muted="#8c959f",
    text_accent="#0969da",
    accent_primary="#0969da",
    accent_secondary="#8250df",
    accent_success="#1a7f37",
    accent_warning="#9a6700",
    accent_error="#cf222e",
    accent_info="#218bff",
    border_default="#d0d7de",
    border_active="#0969da",
    border_focus="#8250df",
    state_thinking="#8250df",
    state_executing="#0969da",
    state_done="#1a7f37",
    state_error="#cf222e",
    syntax_keyword="#cf222e",
    syntax_string="#0969da",
    syntax_comment="#656d76",
    syntax_function="#8250df",
    syntax_number="#218bff",
    syntax_operator="#cf222e",
)

