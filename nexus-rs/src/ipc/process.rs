// Allow dead_code for Phase 1a — BackendState variants will be used in Phase 1b TUI.
#![allow(dead_code)]

//! Python subprocess lifecycle manager.
//!
//! Locates the Python runtime on PATH, spawns the ACP backend as a
//! subprocess (`python -m nexus_agent.backend --acp`), and manages
//! its lifecycle (start, health check, graceful shutdown, force kill).

use std::time::Duration;
use tokio::process::{Child, ChildStdin, ChildStdout, Command};
use tokio::time::timeout;

// ── Types ─────────────────────────────────────────────────────────

/// Describes the state of the Python backend process.
#[derive(Debug)]
pub enum BackendState {
    /// Process has been spawned but not yet initialized.
    Starting,
    /// Process is running and the ACP `init` handshake succeeded.
    Ready { pid: u32 },
    /// Process is running but in a degraded state.
    Degraded { pid: u32, error: String },
    /// Process exited unexpectedly.
    Crashed { exit_code: Option<i32>, stderr: String },
    /// Process was deliberately stopped.
    Stopped,
}

/// Handles the Python backend subprocess lifecycle.
pub struct PythonProcess {
    /// The spawned child process.
    child: Child,
    /// The PID for monitoring.
    pub pid: u32,
    /// Tracks current state.
    pub state: BackendState,
}

// ── Python Discovery ──────────────────────────────────────────────

/// Candidate Python executable names to try on PATH.
pub const PYTHON_CANDIDATES: &[&str] = &[
    "python3",
    "python",
    "python3.12",
    "python3.11",
    "python3.10",
    "py",
];

/// Locate a suitable Python 3 executable on PATH.
fn which_python(candidate: &str) -> bool {
    std::process::Command::new(candidate)
        .arg("--version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Find a Python 3.10+ executable on PATH.
pub fn find_python() -> Result<String, String> {
    for candidate in PYTHON_CANDIDATES {
        if which_python(candidate) {
            return Ok(candidate.to_string());
        }
    }
    Err(
        "Python 3.10+ not found on PATH. Install it from https://python.org".to_string(),
    )
}

// ── Process Lifecycle ─────────────────────────────────────────────

impl PythonProcess {
    /// Spawn the Python backend subprocess with `--acp`.
    ///
    /// Uses `tokio::process::Command` for async spawning. Returns the
    /// process handle along with the stdin/stdout pipes for ACP IPC.
    pub async fn spawn(
        workspace: &str,
        model: Option<&str>,
        provider: Option<&str>,
    ) -> Result<(Self, ChildStdin, ChildStdout), String> {
        let python = find_python()?;

        let mut cmd = Command::new(&python);
        cmd.arg("-m")
            .arg("nexus_agent.backend")
            .arg("--acp")
            .arg("--workspace")
            .arg(workspace)
            .stdin(std::process::Stdio::piped())   // ACP reads stdin for commands
            .stdout(std::process::Stdio::piped())  // ACP writes events/responses to stdout
            .stderr(std::process::Stdio::inherit()); // Python stderr goes to terminal

        if let Some(m) = model {
            cmd.arg("--model").arg(m);
        }
        if let Some(p) = provider {
            cmd.arg("--provider").arg(p);
        }

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn Python backend: {e}"))?;

        let pid = child.id().ok_or("Failed to get child PID")?;
        let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;

        let process = Self {
            child,
            pid,
            state: BackendState::Starting,
        };

        Ok((process, stdin, stdout))
    }

    /// Non-blocking check: is the backend process still alive?
    pub fn is_alive(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(Some(status)) => {
                self.state = BackendState::Crashed {
                    exit_code: status.code(),
                    stderr: String::new(),
                };
                false
            }
            Ok(None) => true,
            Err(_) => false,
        }
    }

    /// Mark the process as ready after a successful ACP init handshake.
    pub fn mark_ready(&mut self) {
        self.state = BackendState::Ready { pid: self.pid };
    }

    /// Mark the process as degraded with an error message.
    pub fn mark_degraded(&mut self, error: String) {
        self.state = BackendState::Degraded {
            pid: self.pid,
            error,
        };
    }

    /// Gracefully shut down the backend process.
    ///
    /// The caller should send an ACP `stop` message first, then call this
    /// to wait for the process to exit. This method waits up to
    /// `kill_timeout`, then force-kills if the process hasn't exited.
    pub async fn shutdown(&mut self, kill_timeout: Duration) -> bool {
        // Wait for process to exit (it should be shutting down from ACP stop)
        match timeout(kill_timeout, self.child.wait()).await {
            Ok(Ok(status)) => {
                self.state = BackendState::Stopped;
                status.success()
            }
            _ => {
                // Process didn't exit in time — force kill
                let _ = self.child.kill().await;
                // Reap after kill
                let _ = self.child.wait().await;
                self.state = BackendState::Stopped;
                false
            }
        }
    }

    /// Return a reference to the current state.
    pub fn state(&self) -> &BackendState {
        &self.state
    }
}
