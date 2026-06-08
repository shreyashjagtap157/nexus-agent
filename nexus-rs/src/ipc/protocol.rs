//! ACP protocol types — JSON-RPC 2.0 request/response/notification structures.
//!
//! Transport: Newline-delimited JSON (NDJSON) on stdin/stdout.
//!
//! - Requests are sent from Rust → Python on Python's stdin.
//! - Notifications are streamed Python → Rust on Python's stdout.
//! - Final responses are sent Python → Rust on Python's stdout.

// Allow dead_code for Phase 1a — these types will be fully wired in Phase 1b+.
#![allow(dead_code)]

use serde::{Deserialize, Serialize};
use serde_json::Value;

// ── Request (Rust → Python) ──────────────────────────────────────────

/// A JSON-RPC 2.0 request sent to the Python backend.
#[derive(Debug, Serialize)]
pub struct AcpRequest {
    pub jsonrpc: String,
    pub id: u64,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
}

impl AcpRequest {
    /// Create a generic request with auto-incremented ID.
    pub fn new(id: u64, method: &str, params: Option<Value>) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        }
    }

    /// Initialize the agent backend with workspace and config.
    ///
    /// Sent once at startup after spawning the Python process.
    pub fn init(id: u64, workspace: &str, model: Option<&str>, config: Option<Value>) -> Self {
        let mut params = serde_json::json!({"workspace": workspace});
        if let Some(m) = model {
            params["model"] = serde_json::json!(m);
        }
        if let Some(cfg) = config {
            params["config"] = cfg;
        }
        Self::new(id, "init", Some(params))
    }

    /// Send a prompt to the agent for processing.
    pub fn prompt(id: u64, text: &str) -> Self {
        Self::new(id, "prompt", Some(serde_json::json!({"text": text})))
    }

    /// Get the current agent status.
    pub fn get_status(id: u64) -> Self {
        Self::new(id, "get_status", None)
    }

    /// Stop the agent session gracefully.
    pub fn stop(id: u64) -> Self {
        Self::new(id, "stop", None)
    }

    /// Execute a slash command.
    pub fn command(id: u64, cmd: &str) -> Self {
        Self::new(id, "command", Some(serde_json::json!({"cmd": cmd})))
    }

    /// List memories from the backend.
    pub fn memory_list(id: u64, category: Option<&str>, limit: usize, offset: usize) -> Self {
        let mut params = serde_json::json!({"limit": limit, "offset": offset});
        if let Some(cat) = category {
            params["category"] = serde_json::json!(cat);
        }
        Self::new(id, "memory_list", Some(params))
    }

    /// Search memories by query text.
    pub fn memory_search(id: u64, query: &str, limit: usize) -> Self {
        Self::new(id, "memory_search", Some(serde_json::json!({"query": query, "limit": limit})))
    }

    /// Get memory system statistics.
    pub fn memory_stats(id: u64) -> Self {
        Self::new(id, "memory_stats", None)
    }

    /// Get current usage and cost tracking data.
    pub fn get_usage(id: u64) -> Self {
        Self::new(id, "get_usage", None)
    }

    /// Serialize to a single NDJSON line.
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }
}

// ── Response (Python → Rust) ────────────────────────────────────────

/// A JSON-RPC 2.0 error object.
#[derive(Debug, Deserialize, Clone)]
pub struct AcpError {
    pub code: i64,
    pub message: String,
}

impl std::fmt::Display for AcpError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[{}] {}", self.code, self.message)
    }
}

/// A JSON-RPC 2.0 response from the Python backend.
#[derive(Debug, Deserialize)]
pub struct AcpResponse {
    pub jsonrpc: String,
    #[serde(default)]
    pub id: Option<Value>,
    #[serde(default)]
    pub result: Option<Value>,
    #[serde(default)]
    pub error: Option<AcpError>,
}

/// A JSON-RPC 2.0 notification (streamed event with no id field).
#[derive(Debug, Deserialize)]
pub struct AcpNotification {
    #[serde(default)]
    pub jsonrpc: Option<String>,
    pub method: String,
    #[serde(default)]
    pub params: Option<Value>,
}

// ── Parsed Event (either notification or response) ──────────────────

/// A parsed line from the ACP stream — either a streaming notification
/// or a final response to a previously sent request.
#[derive(Debug)]
pub enum AcpEvent {
    /// Streaming event (no `id` field).
    Notification {
        method: String,
        params: Option<Value>,
    },
    /// Final response to a request (has `id` field).
    Response {
        id: u64,
        result: Option<Value>,
        error: Option<AcpError>,
    },
}

impl AcpEvent {
    /// Parse a single NDJSON line into a typed ACP event.
    pub fn from_json(line: &str) -> Result<Self, serde_json::Error> {
        let value: Value = serde_json::from_str(line)?;

        // Notifications have a "method" field but no "id" field.
        let is_notification = value.get("method").is_some() && value.get("id").is_none();

        if is_notification {
            let notification: AcpNotification = serde_json::from_value(value)?;
            Ok(AcpEvent::Notification {
                method: notification.method,
                params: notification.params,
            })
        } else {
            let response: AcpResponse = serde_json::from_value(value)?;
            let id = response
                .id
                .as_ref()
                .and_then(|v| v.as_u64())
                .unwrap_or(0);
            Ok(AcpEvent::Response {
                id,
                result: response.result,
                error: response.error,
            })
        }
    }
}

// ── Well-known event types (from Python backend) ────────────────────

/// Known ACP event type constants.
pub mod event_type {
    pub const CONTENT_CHUNK: &str = "content_chunk";
    pub const CONTENT_COMPLETE: &str = "content_complete";
    pub const THINKING: &str = "thinking";
    pub const TOOL_CALL: &str = "tool_call";
    pub const TOOL_RESULT: &str = "tool_result";
    pub const ERROR: &str = "error";
    pub const STATE_CHANGE: &str = "state_change";
    pub const DONE: &str = "done";
    pub const COST_UPDATE: &str = "cost_update";
}
