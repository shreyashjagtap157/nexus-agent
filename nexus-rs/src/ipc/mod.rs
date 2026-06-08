//! IPC module — Agent Client Protocol (ACP) over stdin/stdout.
//!
//! Communicates with the Python agent backend via JSON-RPC 2.0
//! over newline-delimited JSON (NDJSON) on subprocess pipes.

pub mod acp_client;
pub mod process;
pub mod protocol;
