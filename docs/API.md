# NexusAgent API Reference

> **Version:** 0.1.0  
> **Base URL:** `http://127.0.0.1:7860` (local GUI server)

NexusAgent exposes three API surfaces:
1. **REST API** — JSON over HTTP for status, models, sessions, tools
2. **WebSocket** — Real-time streaming chat with the agent
3. **MCP Protocol** — Model Context Protocol over stdio

---

## GUI Server

### Starting the GUI

```bash
nexus gui                          # Default port 7860
nexus gui --port 9000             # Custom port
nexus gui --host 0.0.0.0          # Bind to all interfaces
nexus gui --no-browser            # Skip auto-open browser
nexus gui --workspace /path       # Set workspace directory
```

---

## REST API

### `GET /api/status`

Returns the current status of the agent core.

**Response:**
```json
{
  "app_name": "NexusAgent",
  "version": "0.1.0",
  "model_loaded": true,
  "model_name": "llama-3.1-8b",
  "runtime": "llama-cpp",
  "gpu_backend": "cuda",
  "workspace": "/path/to/workspace",
  "active_session_id": "sess_abc123",
  "hardware": {
    "cpu": "AMD Ryzen 9 7950X",
    "ram_total": "64 GB",
    "ram_available": "32 GB",
    "ram_percent": 50.0,
    "gpu": "NVIDIA RTX 4090",
    "vram": "24 GB",
    "npu": "Not detected",
    "recommended": "70B+ (Q4 quantization)"
  }
}
```

---

### `GET /api/models`

Lists all discovered GGUF and ONNX models in `models_dir`.

**Response:**
```json
[
  {
    "name": "llama-3.1-8b-Q4_K_M",
    "filename": "llama-3.1-8b-Q4_K_M.gguf",
    "path": "/home/user/models/llama-3.1-8b-Q4_K_M.gguf",
    "size_str": "4.9 GB",
    "quantization": "Q4_K_M",
    "format": "gguf"
  }
]
```

---

### `POST /api/models/load`

Load a GGUF model into memory via the local engine.

**Request body:**
```json
{
  "model_path": "/path/to/model.gguf",
  "gpu_layers": -1,
  "context_size": 4096,
  "threads": 0,
  "flash_attention": true,
  "unified_kv_cache": true,
  "kv_quant_type": "f16"
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Successfully loaded model: llama-3.1-8b-Q4_K_M",
  "model_name": "llama-3.1-8b-Q4_K_M",
  "warning": null
}
```

**Response (guardrail blocked):**
```json
{
  "detail": "⚠️ WARNING: Model size (32 GB) exceeds the balanced guardrail limit (85% of memory budget: 54.4 GB)..."
}
```

---

### `POST /api/config/update`

Update active configuration values at runtime.

**Request body:**
```json
{
  "effort_level": "high",
  "goal": "Refactor the authentication module",
  "guardrails": "strict"
}
```

**Response:**
```json
{
  "success": true,
  "config": { ... }
}
```

---

### `GET /api/sessions`

List all saved conversation sessions.

**Response:**
```json
[
  {
    "id": "sess_abc123",
    "title": "Auth module refactor",
    "created": "2026-05-30T10:00:00",
    "message_count": 42,
    "model": "llama-3.1-8b",
    "provider": "local"
  }
]
```

---

### `POST /api/sessions/create`

Create a new conversation session.

**Request body:**
```json
{
  "title": "My new session"
}
```

**Response:**
```json
{
  "session_id": "sess_xyz789",
  "title": "My new session"
}
```

---

### `GET /api/sessions/{session_id}`

Get the message history for a session.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "messages": [
    { "role": "user", "content": "Hello", "timestamp": 1717056000 },
    { "role": "assistant", "content": "Hi! How can I help?", "timestamp": 1717056001 }
  ]
}
```

---

### `GET /api/tasks`

Get the current hierarchical task graph state.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "root_id": "task_root",
  "progress": { "completed": 3, "total": 8 },
  "nodes": {
    "task_1": { "title": "Design auth schema", "status": "done", "children": [] },
    "task_2": { "title": "Implement auth", "status": "in_progress", "children": ["task_3"] }
  },
  "markdown": "# Task Graph\n## task_1: Design auth schema ✓\n..."
}
```

---

### `GET /api/nla/{session_id}`

Retrieve NLA reasoning telemetry logs.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "records": [
    {
      "step": 1,
      "thought": "The user wants to refactor auth...",
      "confidence": 0.85,
      "tool_used": null,
      "timestamp": "2026-05-30T10:00:00Z"
    }
  ],
  "summary": "Session used 12 NLA reasoning steps across 5 tool calls."
}
```

---

### `POST /api/debate`

Trigger parallel multi-agent debate reviews on code changes.

**Response:**
```json
{
  "consensus_score": 0.82,
  "final_approved": true,
  "scores": { "security": 0.9, "performance": 0.75, "correctness": 0.85 },
  "summary": "Code approved with minor performance suggestions.",
  "issues": ["Consider caching repeated auth lookups"],
  "recommendations": ["Add a TTL to the token cache", "Use a faster hash for session IDs"]
}
```

---

### `POST /api/verify`

Run the DevOps verification pipeline (linters, tests, secrets scan).

**Response:**
```json
{
  "success": true,
  "test_framework": "pytest",
  "tests_passed": 142,
  "linters_passed": true,
  "secrets_found": [],
  "vulnerabilities": [],
  "traceback_analysis": "No traceback errors found."
}
```

---

### `POST /api/commit`

Auto-generate a conventional commit message from staged changes.

**Response:**
```json
{
  "message": "feat(auth): add JWT refresh token with sliding expiry"
}
```

---

## WebSocket API

### `WebSocket /api/ws/{session_id}`

Real-time streaming chat. Connect with a `session_id` to send prompts and receive events.

**Client → Server (send):**
```json
{
  "prompt": "Refactor the database connection pooling",
  "mode": "auto"
}
```

**Server → Client (events):**

```json
// Thinking indicator
{ "type": "thinking", "content": "Analyzing code structure..." }

// Streamed text chunk
{ "type": "chunk", "content": "I suggest creating a " }

// Tool call notification
{ "type": "tool_call", "name": "ReadFile", "arguments": {"path": "db.py"} }

// Tool result
{ "type": "tool_result", "name": "ReadFile", "success": true, "output": "..." }

// Error
{ "type": "error", "content": "Permission denied" }

// Done (agent finished)
{ "type": "done", "iterations": 7 }
```

**Reconnection:** If the connection drops, reconnect to the same `session_id` to resume from the last checkpoint.

---

## MCP Protocol

NexusAgent implements the Model Context Protocol over stdio for tool discovery.

### Running as an MCP Server

```bash
nexus mcp serve --transport stdio
```

### Connecting to an External MCP Server

```bash
nexus mcp add --name my-server --command /path/to/mcp-server --args arg1
```

### Available MCP Tools

When NexusAgent acts as an MCP server, it exposes these tools:
- `read_file(path: string)` — Read file contents
- `write_file(path: string, content: string)` — Write or overwrite a file
- `search_files(pattern: string, path?: string)` — Grep-like search in files
- `list_directory(path: string)` — List directory contents
- `shell(command: string)` — Execute a sandboxed shell command
- `git(args: string[])` — Execute a git subcommand

---

## Error Codes

| HTTP Status | Meaning |
|------------|---------|
| 200 | Success |
| 400 | Bad request (e.g., guardrail blocked model load) |
| 413 | Request body too large (>10MB) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

## Rate Limits

- API endpoints: **100 requests/minute** per client IP
- WebSocket: Unlimited while connected
- No rate limit on local GUI (localhost only)

---

## CORS

CORS is enabled only for `http://127.0.0.1` and `http://localhost` (local development). Production deployments behind a reverse proxy should configure CORS headers at the proxy level.