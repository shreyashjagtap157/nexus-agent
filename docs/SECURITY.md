# Security Policy

> **Last Updated:** 2026-05-31  
> **Severity Classification:** Critical → Low (CVSS-based)

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

**Do NOT** report security vulnerabilities via public GitHub issues.

Instead:
1. Email: `security@nexus-agent.dev` (if available)  
2. Or use GitHub's **Private vulnerability reporting** (Security tab)
3. Include details about the affected component and reproduction steps

We aim to respond within **48 hours** and provide a fix within **14 days** for critical issues.

---

## Security Model

### Shell Command Execution

All shell commands go through `core/sandbox.py` which:
1. Uses `shlex.split()` to parse command strings into list arguments
2. Executes via `subprocess.run(args, shell=False)` — **never `shell=True`**
3. Applies regex-based `dangerous_indicators` pattern detection
4. Supports three modes: `suggest` (confirm each), `ask` (confirm sensitive), `auto` (skip confirmations)

**The sandbox is the primary security layer.** There is no command allowlist or denylist — the sandbox evaluates risk dynamically.

### Command Injection Prevention

- All user-provided strings are treated as untrusted input
- `shlex.split()` is used for safe argument parsing
- `subprocess.run()` uses `shell=False` exclusively
- No string interpolation into shell commands
- Regex patterns in `dangerous_indicators` catch common injection attempts

### Git Worktree Isolation

- Git operations use `git worktree` to isolate changes
- The agent operates on a dedicated worktree, never directly on `.git`
- Session-scoped git state prevents cross-session contamination

### API Key Storage

- API keys are stored in `~/.nexus-agent/auth.json` (file permissions: 600)
- Keys are never logged, printed, or stored in config files
- `AuthStore` provides encrypted-at-rest key management

### Web Server (GUI)

The FastAPI GUI server:
- Binds to `127.0.0.1:7860` by default (localhost only)
- CORS restricted to `http://127.0.0.1` and `http://localhost`
- Rate limiting: **100 requests/minute** per client IP
- Request body size limit: **10MB**
- CSP headers: strict `self` policy
- `X-Frame-Options: DENY` to prevent clickjacking

**Production deployment:** Always run behind a TLS-terminating reverse proxy (nginx, Caddy, etc.).

---

## Known Limitations

### Local Model Hosting

When running GGUF models locally:
- Model files are loaded directly into RAM/VRAM
- No process-level memory sandboxing is applied to the LLM inference process
- Users should only load GGUF files from trusted sources (e.g., HuggingFace with verified checksums)

### Windows PowerShell

On Windows, some native commands are executed via PowerShell. These are subject to PowerShell's execution policy and are additionally sandboxed through the subprocess module.

---

## Dependency Security

- All dependencies are pinned to specific versions in `pyproject.toml`
- Run `pip-audit` periodically to check for known CVEs:

```bash
pip install pip-audit
pip-audit
```

- CI runs `pip-audit` on every pull request

---

## Secrets Scanning

The DevOps pipeline (`nexus devops`) scans for common secret patterns:

```
aws_access_key
aws_secret_key
api_key
secret_key
password
token
private_key
client_secret
```

If secrets are detected, the pipeline fails and reports the file path and line number.

**Never commit credentials.** Use `nexus config set` or environment variables instead.

---

## Environment Variables

| Variable | Purpose | Security |
|----------|---------|----------|
| `NEXUS_API_KEY_*` | Provider API keys | Store in shell profile, not in code |
| `NEXUS_DATA_DIR` | Override data directory | Ensure filesystem permissions |
| `NEXUS_MODELS_DIR` | Override model directory | Ensure filesystem permissions |

---

## Compliance

- All `except Exception` clauses have been eliminated from the codebase
- The codebase is scanned for command injection vulnerabilities
- FTS5 queries use parameterized inputs (not string interpolation)
- No eval() or exec() calls remain in the codebase