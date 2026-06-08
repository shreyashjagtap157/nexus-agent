//! Nexus — offline-first AI coding agent CLI (Rust core).
//!
//! Phase 1b: Ratatui TUI with:
#![allow(dead_code)]
//! - Multi-pane layout (chat, status, input)
//! - Streaming content with block detection
//! - Keyboard-driven input with history
//! - Task inspector overlay (Ctrl+T)
//! - Command palette overlay (Ctrl+P)
//! - Theme system (TOML-defined)
//!
//! Usage:
//!   nexus chat                          # Default mode
//!   nexus chat --model llama3-8b-q4     # Specify model
//!   nexus chat --provider anthropic     # Use cloud provider
//!   nexus chat --workspace /path        # Set workspace
//!   nexus doctor                        # Run diagnostics

use clap::{Parser, Subcommand};
use std::io::Write;
use std::time::Duration;
use tracing_subscriber::EnvFilter;

mod app;
mod config;
mod ipc;
mod tui;

use app::{App, AppEvent, AppPhase, Command, BackendStatus};
use ipc::acp_client::AcpClient;
use ipc::process;
use ipc::process::PythonProcess;
use ipc::protocol::{AcpEvent, event_type};

// ── CLI Argument Definitions ─────────────────────────────────────────

/// Offline-first AI coding agent.
#[derive(Parser, Debug)]
#[command(name = "nexus", version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Start the interactive agent REPL.
    Chat {
        /// Path to a local GGUF model file or model alias.
        #[arg(long)]
        model: Option<String>,

        /// Cloud provider to use (anthropic, openai, etc.).
        #[arg(long)]
        provider: Option<String>,

        /// Workspace directory (defaults to current directory).
        #[arg(long, default_value = ".")]
        workspace: String,

        /// Config file path.
        #[arg(long)]
        config: Option<String>,

        /// Skip ACP init handshake (for testing).
        #[arg(long, hide = true)]
        no_init: bool,
    },

    /// Run diagnostics.
    Doctor {
        /// Verbose output.
        #[arg(long, short)]
        verbose: bool,
    },

    /// Print version and exit.
    #[command(hide = true)]
    Version,
}

// ── Entry Point ─────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    // Initialize structured logging
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Chat {
            model,
            provider,
            workspace,
            config: _config,
            no_init,
        } => {
            run_chat(&workspace, model.as_deref(), provider.as_deref(), no_init).await;
        }
        Commands::Doctor { verbose } => {
            run_doctor(verbose).await;
        }
        Commands::Version => {
            println!("nexus {}", env!("CARGO_PKG_VERSION"));
        }
    }
}

// ── Chat Subcommand ─────────────────────────────────────────────────

async fn run_chat(workspace: &str, model: Option<&str>, provider: Option<&str>, no_init: bool) {
    // 0. Load config and create App state
    let cfg = config::loader::load_config()
        .with_cli_overrides(
            model.map(|s| s.to_string()),
            provider.map(|s| s.to_string()),
            Some(workspace.to_string()),
        );
    let mut app = App::new(cfg);

    // 1. Spawn the Python backend process
    eprintln!("[nexus] Starting Python backend...");
    let (mut process, stdin, stdout) = match PythonProcess::spawn(workspace, model, provider).await
    {
        Ok(result) => result,
        Err(e) => {
            eprintln!("[nexus] ERROR: {e}");
            std::process::exit(1);
        }
    };
    eprintln!("[nexus] Python backend started (pid: {})", process.pid);

    // 2. Create the ACP client
    let mut client = AcpClient::new(stdin, stdout);

    // 3. Initialize TUI engine
    let (mut tui_engine, mut tui_events) = match tui::engine::TuiEngine::new() {
        Ok(engine) => engine,
        Err(e) => {
            eprintln!("[nexus] TUI init error: {e}");
            eprintln!("[nexus] Falling back to text mode...");
            // Fall through to text-mode loop below
            run_text_mode(&mut client, &mut process, workspace, model, no_init).await;
            return;
        }
    };

    // 4. Spawn keyboard event reader in background
    let event_tx = tui_engine.event_tx.clone();
    tokio::spawn(async move {
        tui::engine::TuiEngine::run_event_loop(event_tx).await;
    });

    // 5. Send init handshake
    if !no_init {
        eprintln!("[nexus] Initializing agent...");
        let init_id = client
            .init(workspace, model, None)
            .await
            .expect("Failed to send init request");

        let mut init_ok = false;
        while let Some(event) = client.events.recv().await {
            match event {
                AcpEvent::Response { id, result, error } if id == init_id => {
                    if let Some(e) = error {
                        eprintln!("[nexus] Init error: {e}");
                        process.mark_degraded(e.to_string());
                        // Send backend error to app
                        let _ = tui_engine.event_tx
                            .send(AppEvent::BackendError(e.to_string()))
                            .await;
                    } else {
                        process.mark_ready();
                        init_ok = true;
                        let _ = tui_engine.event_tx
                            .send(AppEvent::BackendEvent(BackendStatus::Connected))
                            .await;
                        // Send init response to app
                        if let Some(r) = result {
                            let _ = tui_engine.event_tx
                                .send(AppEvent::AcpResponse { id, result: Some(r) })
                                .await;
                        }
                    }
                    break;
                }
                _ => {}
            }
        }

        if !init_ok {
            app.phase = AppPhase::Error;
            app.error_message = Some("Agent initialization failed".to_string());
        }
    } else {
        process.mark_ready();
        let _ = tui_engine.event_tx
            .send(AppEvent::BackendEvent(BackendStatus::Connected))
            .await;
    }

    // 6. Main event loop
    let mut current_prompt_id: Option<u64> = None;
    // Pending memory request IDs for ACP response routing
    let mut pending_memory_list_id: Option<u64> = None;
    let mut pending_memory_stats_id: Option<u64> = None;

    loop {
        // Check if we should quit
        if app.should_quit || app.phase == AppPhase::Exiting {
            break;
        }

        // Check backend health
        if !process.is_alive() {
            let _ = tui_engine
                .event_tx
                .send(AppEvent::BackendError("Backend process exited".to_string()))
                .await;
            // Give the user a moment to see the error
            tokio::select! {
                Some(_) = tui_events.recv() => {},
                _ = tokio::time::sleep(Duration::from_millis(200)) => {},
            }
            break;
        }

        // Process events from TUI and ACP
        tokio::select! {
            // TUI events (keyboard, tick)
            Some(app_event) = tui_events.recv() => {
                let cmd = app.update(app_event);

                // Handle commands returned from app.update()
                match cmd {
                    Command::SendAcp(text) => {
                        if let Ok(id) = client.prompt(&text).await {
                            current_prompt_id = Some(id);
                        }
                    }
                    Command::Quit => {
                        app.phase = AppPhase::Exiting;
                        break;
                    }
                    Command::ToggleInspector => {
                        app.inspector_visible = !app.inspector_visible;
                    }
                    Command::TogglePalette => {
                        app.palette_open = !app.palette_open;
                    }
                    Command::CycleLayout => {
                        app.cycle_layout();
                    }
                    Command::ChangeTheme(name) => {
                        app.theme = crate::tui::render::themes::load_theme(&name, None);
                    }
                    Command::OpenMenu(menu) => {
                        let _ = client.command(&format!("/menu {menu}")).await;
                    }
                    Command::CopyToClipboard(text) => {
                        #[cfg(windows)]
                        let _ = std::process::Command::new("clip")
                            .stdin(std::process::Stdio::piped())
                            .spawn()
                            .and_then(|mut c| {
                                use std::io::Write;
                                c.stdin.take().unwrap().write_all(text.as_bytes())
                            });
                        #[cfg(not(windows))]
                        let _ = std::process::Command::new("pbcopy")
                            .stdin(std::process::Stdio::piped())
                            .spawn()
                            .and_then(|mut c| {
                                use std::io::Write;
                                c.stdin.take().unwrap().write_all(text.as_bytes())
                            });
                    }
                    Command::ToggleMemoryBrowser => {
                        app.memory_browser.visible = !app.memory_browser.visible;
                        if app.memory_browser.visible {
                            let req_id = client.next_id();
                            let req = ipc::protocol::AcpRequest::memory_list(req_id, None, 100, 0);
                            let _ = client.send(&req).await;
                            pending_memory_list_id = Some(req_id);
                            let stats_id = client.next_id();
                            let stats_req = ipc::protocol::AcpRequest::memory_stats(stats_id);
                            let _ = client.send(&stats_req).await;
                            pending_memory_stats_id = Some(stats_id);
                        }
                    }
                    _ => {}
                }
            }

            // ACP events from Python backend
            Some(acp_event) = client.events.recv() => {
                match acp_event {
                    AcpEvent::Notification { method, params } => {
                        let app_event = AppEvent::AcpNotification {
                            method,
                            data: params,
                        };
                        app.update(app_event);
                    }
                    AcpEvent::Response { id, result, error } => {
                        // Route memory responses
                        if Some(id) == pending_memory_list_id {
                            pending_memory_list_id = None;
                            if let Some(r) = result {
                                let entries = r.get("entries").cloned().unwrap_or(serde_json::json!([]));
                                let count = r.get("count").and_then(|c| c.as_u64()).unwrap_or(0) as usize;
                                let entries: Vec<serde_json::Value> = serde_json::from_value(entries).unwrap_or_default();
                                let app_event = AppEvent::MemoryList {
                                    result: app::MemoryListResult { entries, count },
                                };
                                app.update(app_event);
                            } else if let Some(e) = error {
                                app.memory_browser.set_error(e.to_string());
                            }
                            continue;
                        }
                        if Some(id) == pending_memory_stats_id {
                            pending_memory_stats_id = None;
                            if let Some(r) = result {
                                let app_event = AppEvent::MemoryStats { stats: r };
                                app.update(app_event);
                            }
                            continue;
                        }

                        if let Some(e) = error {
                            let app_event = AppEvent::BackendError(e.to_string());
                            app.update(app_event);
                        } else {
                            let app_event = AppEvent::AcpResponse {
                                id,
                                result,
                            };
                            app.update(app_event);
                        }
                        // Check if this matches the current prompt
                        if Some(id) == current_prompt_id {
                            if app.phase == AppPhase::Processing {
                                app.phase = AppPhase::Ready;
                            }
                            current_prompt_id = None;
                        }
                    }
                }
            }

            // Draw at 60fps
            _ = tokio::time::sleep(Duration::from_millis(16)) => {
                // Tick for animations
                app.update(AppEvent::Tick);
            }
        }

        // Draw the current frame
        let _ = tui_engine.draw(&app);
    }

    // 7. Graceful shutdown
    eprintln!("\n[nexus] Shutting down backend...");
    let _ = client.stop().await;
    process.shutdown(Duration::from_secs(5)).await;
    let _ = tui_engine.restore();
    eprintln!("[nexus] Goodbye.");
}

// ── Text Mode Fallback ──────────────────────────────────────────────

/// Phase 1a-style text passthrough, used when TUI init fails.
async fn run_text_mode(
    client: &mut AcpClient,
    process: &mut PythonProcess,
    workspace: &str,
    model: Option<&str>,
    no_init: bool,
) {
    // Init handshake
    if !no_init {
        let init_id = client
            .init(workspace, model, None)
            .await
            .expect("Failed to send init request");
        while let Some(event) = client.events.recv().await {
            if let AcpEvent::Response { id, error, .. } = event {
                if id == init_id {
                    if let Some(e) = error {
                        eprintln!("[nexus] Init error: {e}");
                        process.mark_degraded(e.to_string());
                    } else {
                        process.mark_ready();
                    }
                    break;
                }
            }
        }
    } else {
        process.mark_ready();
    }

    eprintln!("[nexus] Interactive session (text mode). Type /quit to exit.\n");

    let stdin_reader = tokio::io::BufReader::new(tokio::io::stdin());
    let mut lines = tokio::io::AsyncBufReadExt::lines(stdin_reader);

    loop {
        if !process.is_alive() {
            eprintln!("\n[nexus] Backend process exited.");
            break;
        }

        eprint!("> ");
        let _ = std::io::Write::flush(&mut std::io::stderr());

        let input = match lines.next_line().await {
            Ok(Some(line)) => line.trim().to_string(),
            Ok(None) => {
                let _ = client.stop().await;
                break;
            }
            Err(e) => {
                eprintln!("\n[nexus] Input error: {e}");
                break;
            }
        };

        if input.is_empty() {
            continue;
        }

        match input.to_lowercase().as_str() {
            "/quit" | "/exit" => {
                let _ = client.stop().await;
                break;
            }
            "/help" => {
                println!("Commands: /help /quit /exit /status");
                continue;
            }
            "/status" => {
                let id = client.next_id();
                let req = ipc::protocol::AcpRequest::get_status(id);
                let _ = client.send(&req).await;
                while let Some(event) = client.events.recv().await {
                    if let AcpEvent::Response { id: rid, result, .. } = event {
                        if rid == id {
                            if let Some(r) = result {
                                println!("Status: {}", serde_json::to_string_pretty(&r).unwrap());
                            }
                            break;
                        }
                    }
                }
                continue;
            }
            _ => {}
        }

        let prompt_id = match client.prompt(&input).await {
            Ok(id) => id,
            Err(e) => {
                eprintln!("[nexus] Send error: {e}");
                continue;
            }
        };

        loop {
            tokio::select! {
                Some(event) = client.events.recv() => {
                    match event {
                        AcpEvent::Notification { method, params } => {
                            match method.as_str() {
                                event_type::CONTENT_CHUNK => {
                                    if let Some(text) = params.as_ref()
                                        .and_then(|p| p.get("data"))
                                        .and_then(|d| d.as_str())
                                    {
                                        print!("{text}");
                                        std::io::stdout().flush().ok();
                                    }
                                }
                                event_type::THINKING => {
                                    if let Some(text) = params.as_ref()
                                        .and_then(|p| p.get("data"))
                                        .and_then(|d| d.as_str())
                                    {
                                        eprintln!("[thinking] {text}");
                                    }
                                }
                                event_type::TOOL_CALL => {
                                    if let Some(name) = params.as_ref()
                                        .and_then(|p| p.get("data"))
                                        .and_then(|d| d.get("name"))
                                        .and_then(|n| n.as_str())
                                    {
                                        eprintln!("[tool] {name}");
                                    }
                                }
                                event_type::ERROR => {
                                    if let Some(text) = params.as_ref()
                                        .and_then(|p| p.get("data"))
                                        .and_then(|d| d.as_str())
                                    {
                                        eprintln!("[error] {text}");
                                    }
                                }
                                _ => {}
                            }
                        }
                        AcpEvent::Response { id: rid, result: Some(r), .. } if rid == prompt_id => {
                            if let Some(status) = r.get("status").and_then(|s| s.as_str()) {
                                if status == "completed" || status == "done" {
                                    println!();
                                }
                            }
                            break;
                        }
                        AcpEvent::Response { id: rid, error: Some(e), .. } if rid == prompt_id => {
                            eprintln!("\n[nexus] Agent error: {e}");
                            break;
                        }
                        _ => {}
                    }
                }
                else => {
                    eprintln!("\n[nexus] Backend disconnected.");
                    break;
                }
            }
        }

        if !process.is_alive() {
            break;
        }
    }

    process.shutdown(Duration::from_secs(5)).await;
}

// ── Doctor Subcommand ─────────────────────────────────────────────

async fn run_doctor(verbose: bool) {
    println!("=== Nexus Doctor ===");
    println!("Version: {}", env!("CARGO_PKG_VERSION"));
    println!();

    println!("[1/5] Python runtime...");
    match process::find_python() {
        Ok(python) => {
            println!("  ✅ Found: {python}");
            if verbose {
                match std::process::Command::new(&python).arg("--version").output() {
                    Ok(out) => {
                        let v = String::from_utf8_lossy(&out.stdout).trim().to_string();
                        println!("     Version: {v}");
                    }
                    Err(e) => println!("     Error: {e}"),
                }
            }
        }
        Err(e) => println!("  ❌ {e}"),
    }

    println!("\n[2/5] nexus-agent package...");
    if let Ok(python) = process::find_python() {
        match std::process::Command::new(&python)
            .args(["-m", "nexus_agent", "--version"])
            .output()
        {
            Ok(out) if out.status.success() => {
                let v = String::from_utf8_lossy(&out.stdout).trim().to_string();
                println!("  ✅ {v}");
            }
            Ok(out) => {
                let e = String::from_utf8_lossy(&out.stderr).trim().to_string();
                println!("  ❌ Failed: {e}");
            }
            Err(e) => println!("  ❌ Error: {e}"),
        }
    }

    println!("\n[3/5] ACP backend...");
    let cwd = std::env::current_dir().unwrap_or_default();
    match PythonProcess::spawn(cwd.to_str().unwrap_or("."), None, None).await {
        Ok((mut proc, stdin, stdout)) => {
            let mut client = AcpClient::new(stdin, stdout);
            match client.init(cwd.to_str().unwrap_or("."), None, None).await {
                Ok(id) => {
                    let mut ok = false;
                    while let Some(event) = client.events.recv().await {
                        if let AcpEvent::Response { id: rid, result: _, .. } = event {
                            if rid == id {
                                println!("  ✅ Backend responded");
                                ok = true;
                                break;
                            }
                        }
                    }
                    if !ok {
                        println!("  ⚠️  No init response");
                    }
                    proc.shutdown(Duration::from_secs(3)).await;
                }
                Err(e) => {
                    println!("  ❌ Init failed: {e}");
                    let _ = proc.shutdown(Duration::from_secs(3)).await;
                }
            }
        }
        Err(e) => println!("  ❌ {e}"),
    }

    println!("\n[4/5] Workspace...");
    let cwd = std::env::current_dir().unwrap_or_default();
    println!("  ✅ {}", cwd.display());

    println!("\n[5/5] Config...");
    let cfg = config::loader::load_config();
    println!("  Theme: {}", cfg.theme);
    println!("  Provider: {}", cfg.provider);
    if let Some(m) = &cfg.model {
        println!("  Model: {m}");
    }

    println!("\n=== Doctor complete ===");
}
