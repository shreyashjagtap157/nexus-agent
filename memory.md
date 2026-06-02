# Project Memory

## Latest Changes (2026-06-02)
- Welcome display: no longer shows fake context size when no model loaded
- Token tracking: added `PerRequest` class for per-request input/output tokens + elapsed timing, shown after each response like Claude Code
- `/help` expanded: shows full keyboard shortcuts reference (Ctrl+C/D/L/W/U, Enter, Esc, Tab, ↑/↓, /)
- Welcome panel shortcut labels now descriptive ("/help commands  Ctrl+C abort  Ctrl+D exit")
- Multi-pass orchestration: xhigh and max effort levels get automatic planning phase + final review pass
- EFFORT_CONFIG now has `multi_pass` boolean field
- `/runtime` command: added `install`, `reinstall`, `uninstall`, `switch` subcommands with progress reporting
- Wizard: added runtime selection/installation step (Step 2) with CUDA detection
- Config: added `NEXUS_RUNTIME` and `NEXUS_EFFORT_LEVEL` env vars
- Model config HUD fixed: Enter now confirms & loads, Esc properly cancels, mouse clicks parsed
- Effort selector UI fixed: dynamic marker positioning, labels use "Faster"/"Smarter"
- Convention files: AGENTS.md, CLAUDE.md, .github/copilot-instructions.md for cross-agent portability
- Tests: 161 passing

## Instructions for the AI Agent

### Reinstall After Code Updates
- After ANY code change, run `pip install -e .` (or `pip install -e ".[all]"`) to reinstall the package so the `nexus` CLI command reflects the latest changes.
- This ensures imports resolve correctly and the CLI entry point is up to date.

### CLI Testing
- Run `nexus --help` to verify CLI commands.
- Run `nexus chat --help` to verify chat options.
- Run `python -m pytest tests/ -v` to run all tests.

### Code Style
- No comments in code unless absolutely necessary for clarity.
- Use present tense for spinner verbs, past tense for completion messages.
- Dict-based dispatch for slash commands (not match/case).
- Rich markup for terminal rendering, but plain text for raw stdout sections.
- `▸` (U+25B8) for command menu selection marker.
- `> ` (no leading spaces) for user prompt prefix.
- All ANSI escape helpers in renderer.py (save/restore cursor, hide/show, move, clear).

### Package Structure
- `src/nexus_agent/cli/` — CLI rendering and REPL application
- `src/nexus_agent/core/` — Agent logic, planners, executors, orchestrators
- `src/nexus_agent/tools/` — Tool implementations (file ops, git, browser, etc.)
- `src/nexus_agent/llm/` — LLM provider implementations
- `src/nexus_agent/mcp/` — MCP client for external tool servers
- `src/nexus_agent/skills/` — Skill discovery and registration
- `src/nexus_agent/session/` — Session and checkpoint management
- `src/nexus_agent/memory/` — Memory/persistence layer
- `config/` — Configuration files (default.yaml)
- `tests/` — Test suite

### UI Rendering Target
Primary goal: match Claude Code's terminal rendering style exactly.
- Viewport virtualization: only render visible lines, virtualize offscreen content.
- Frame diffing: compute ANSI patches between frames, avoid full redraws.
- Collapsible tool output blocks with expand/collapse via click or keyboard.
- Streaming progressive rendering for assistant messages and tool output.
- Alternate screen buffer for fullscreen mode (`/tui fullscreen`).
- Event-driven rendering from agent execution events.
- Input box anchored at bottom, never scrolls away.
- Focus/verbose view modes.

### Keyboard Shortcuts
- **Ctrl+A** — beginning of line
- **Ctrl+E** — end of line
- **Ctrl+K** — kill to end of line (stored in kill buffer)
- **Ctrl+U** — kill to start of line (stored in kill buffer)
- **Ctrl+Y** — yank (paste kill buffer)
- **Ctrl+L** — clear screen and redraw
- **Ctrl+R** — interactive reverse-i-search history mode
- **Ctrl+G** — external editor ($EDITOR or notepad.exe)
- **Ctrl+V** — clipboard paste (CRLF → LF normalized, large pastes >10K collapsed)
- **Alt+Enter** — insert newline for multi-line input
- **Tab** — command/file menu autocomplete
- **Up/Down** — history navigation (or menu navigation when command menu visible)
- **PgUp/PgDn** — viewport scroll in fullscreen mode

### Known Quirks
- Windows terminals use `\xe0` prefix for arrow keys, Home/End, etc.
- `BEL` = `\x07` for OSC string terminators.
- `ST` = `\033\\` for OSC string terminators (alternative).
- Spinner frame rate: 0.08s cycle (~12.5fps), auto-colors: <10s bold, 10-30s bold yellow, ≥30s bold red.
- Clipboard paste via Ctrl+V preserves newlines (CRLF normalized).

### Command Menu Improvements
- Matching characters highlighted in blue (ANSI `\033[34m`).
- "No commands match" shown when no slash commands match the query.
- Descriptions truncated with `…` when they exceed available width.
