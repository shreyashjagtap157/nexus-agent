//! ACP client — sends JSON-RPC 2.0 requests to the Python backend
//! and receives streaming events and responses over stdio pipes.
//!
//! Architecture:
//! - A background tokio task reads NDJSON lines from the Python process stdout.
//! - Lines are parsed into `AcpEvent` (notification or response) and forwarded
//!   via an `mpsc::UnboundedReceiver` channel.
//! - The main task sends requests by writing to the Python process stdin.

// Allow dead_code for Phase 1a — command() and AcpError::Backend will be used in Phase 1b.
#![allow(dead_code)]

use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStdin, ChildStdout};
use tokio::sync::mpsc;
use std::sync::atomic::{AtomicU64, Ordering};

use super::protocol::{AcpEvent, AcpRequest};

/// ACP client error.
#[derive(Debug, thiserror::Error)]
pub enum AcpError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Serialization error: {0}")]
    Serde(#[from] serde_json::Error),
    #[error("Backend error: {0}")]
    Backend(String),
}

/// Client for communicating with the Python agent backend via ACP.
pub struct AcpClient {
    /// Write handle to the Python process stdin.
    stdin: ChildStdin,
    /// Atomic counter for JSON-RPC request IDs.
    next_id: AtomicU64,
    /// Receiver for parsed ACP events from the reader task.
    pub events: mpsc::UnboundedReceiver<AcpEvent>,
}

impl AcpClient {
    /// Create a new ACP client.
    ///
    /// Spawns a background tokio task that reads NDJSON lines from
    /// `stdout` and forwards parsed `AcpEvent`s to the returned receiver.
    pub fn new(stdin: ChildStdin, stdout: ChildStdout) -> Self {
        let (tx, rx) = mpsc::unbounded_channel();

        // Spawn reader task: reads lines from Python stdout, parses events,
        // sends them through the channel.
        tokio::spawn(async move {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                let trimmed = line.trim().to_string();
                if trimmed.is_empty() {
                    continue;
                }
                match AcpEvent::from_json(&trimmed) {
                    Ok(event) => {
                        if tx.send(event).is_err() {
                            // Receiver dropped — Python process likely exited.
                            break;
                        }
                    }
                    Err(e) => {
                        // Log malformed lines but don't crash.
                        eprintln!("[nexus] ACP parse warning: {e} (line: {trimmed})");
                    }
                }
            }
        });

        Self {
            stdin,
            next_id: AtomicU64::new(1),
            events: rx,
        }
    }

    /// Send a JSON-RPC request to the Python backend.
    pub async fn send(&mut self, request: &AcpRequest) -> Result<(), AcpError> {
        let json = request.to_json()?;
        self.stdin.write_all(json.as_bytes()).await?;
        self.stdin.write_all(b"\n").await?;
        self.stdin.flush().await?;
        Ok(())
    }

    /// Convenience: send an `init` request.
    pub async fn init(
        &mut self,
        workspace: &str,
        model: Option<&str>,
        config: Option<serde_json::Value>,
    ) -> Result<u64, AcpError> {
        let id = self.next_id();
        let req = AcpRequest::init(id, workspace, model, config);
        self.send(&req).await?;
        Ok(id)
    }

    /// Convenience: send a `prompt` request, returns the request ID.
    pub async fn prompt(&mut self, text: &str) -> Result<u64, AcpError> {
        let id = self.next_id();
        let req = AcpRequest::prompt(id, text);
        self.send(&req).await?;
        Ok(id)
    }

    /// Convenience: send a `stop` request.
    pub async fn stop(&mut self) -> Result<u64, AcpError> {
        let id = self.next_id();
        let req = AcpRequest::stop(id);
        self.send(&req).await?;
        Ok(id)
    }

    /// Convenience: send a `command` request.
    pub async fn command(&mut self, cmd: &str) -> Result<u64, AcpError> {
        let id = self.next_id();
        let req = AcpRequest::command(id, cmd);
        self.send(&req).await?;
        Ok(id)
    }

    /// Get the next auto-incrementing request ID.
    pub fn next_id(&self) -> u64 {
        self.next_id.fetch_add(1, Ordering::SeqCst)
    }
}
