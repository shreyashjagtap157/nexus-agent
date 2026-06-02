# NexusAgent CLI Reference

Complete reference for all `nexus` subcommands.

---

## Global Options

```
--model, -m PATH       Path to GGUF model file or model identifier
--provider, -p NAME   LLM provider: local, openai, anthropic, google, groq, etc.
--offline              Force offline mode (local model only)
--gpu-layers N        Number of GPU layers to offload (-1=all, 0=CPU only)
--config, -c PATH     Path to config file
--data-dir PATH        Data directory for sessions/memory
--verbose             Show verbose debug output
--quiet               Suppress non-essential output
--version             Show version and exit
--help, -h            Show help and exit
```

---

## `nexus chat`

Start an interactive chat session (TUI mode).

```bash
nexus chat                          # Interactive TUI
nexus chat --model /path/to/model.gguf
nexus chat --provider openai --model gpt-4o
nexus chat --prompt "Write a quicksort"  # Non-interactive
nexus chat --workspace /project/path
nexus chat --verbose
nexus chat --quiet
```

**Sub-options:**
```
--prompt, -p TEXT      Initial prompt (non-interactive mode)
--workspace, -w PATH   Working directory (default: current directory)
```

---

## `nexus gui`

Launch the web-based GUI dashboard.

```bash
nexus gui                   # Default port 7860
nexus gui --port 9000     # Custom port
nexus gui --host 0.0.0.0  # Bind to all interfaces
nexus gui --no-browser    # Don't auto-open browser
nexus gui --workspace /path
nexus gui --provider openai
nexus gui --model gpt-4o
```

---

## `nexus model`

Manage local GGUF models.

```bash
nexus model list              # List discovered models
nexus model list -d /custom/path  # Scan custom directory
nexus model info <path>       # Show model metadata
```

---

## `nexus session`

Manage agent sessions.

```bash
nexus session list                # List all saved sessions
nexus session resume <session_id> # Resume a session
nexus session checkpoint <desc>   # Create a git worktree snapshot
nexus session rollback [<checkpoint_id>]  # Rollback to checkpoint
```

---

## `nexus config`

Manage configuration.

```bash
nexus config show                    # Show current config
nexus config get                    # Show all config
nexus config get model.provider     # Show specific value
nexus config set model.provider openai  # Set a value
nexus config set local_model.gpu_layers 32
```

---

## `nexus hardware`

Show hardware capabilities for model hosting.

```bash
nexus hardware
# Output:
# CPU: AMD Ryzen 9 7950X
# RAM: 64 GB
# GPU: NVIDIA RTX 4090 (24 GB VRAM)
# Recommended model size: 70B+ (Q4 quantization)
```

---

## `nexus wizard`

Run the interactive first-run setup wizard.

```bash
nexus wizard
```

Steps through: hardware detection, model recommendation, permission/memory/guardrail mode selection, optional cloud API key setup.

---

## `nexus browse`

Browse a URL with headless browser support.

```bash
nexus browse https://github.com --action navigate
nexus browse https://news.ycombinator.com --action read
nexus browse https://example.com --action screenshot
```

---

## `nexus plan`

Generate an implementation plan without making changes (read-only analysis).

```bash
nexus plan "Add OAuth2 authentication to the API"
nexus plan --workspace /my/project "Refactor the database layer"
```

---

## `nexus devops`

Run the DevOps verification pipeline.

```bash
nexus devops                  # Run all checks
nexus devops --workspace /path
```

Checks: linters, test framework detection, secrets scan, traceback analysis.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check output for details) |
| 130 | Interrupted (Ctrl+C) |