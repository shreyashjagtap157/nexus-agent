# NexusAgent — Detailed Execution Roadmap

> **Version:** 0.1.0  
> **Status:** Ready for approval  
> **Total estimated effort:** ~80-100 hours (10-12 days full-time)

---

## PHASE A: CRITICAL SAFETY & STABILITY (Days 1-2)

**Goal:** Eliminate all P0 issues — security holes, crash bugs, vaporware.

### A1: Shell Command Injection Fix (P0) — 3h
**Files:** `tools/shell.py`, `core/sandbox.py`
- [ ] Add input validation and sanitization for all shell commands
- [ ] Replace string-based command construction with `shlex.quote()`
- [ ] Add command allowlist/denylist enforcement
- [ ] Add timeout enforcement on all subprocess calls
- [ ] Fix unsafe `shell=True` usages
- [ ] Add tests for command injection prevention

### A2: Fix Bare Except Clauses (P0-P1) — 2h
**Files:** `core/executor.py`, `gui/server.py`, `tools/browser.py`, `tools/batch_edit.py`, `cli/auth.py`, `session/checkpoint.py`
- [ ] Replace bare `except:` with `except Exception:` in executor.py
- [ ] Narrow broad `except Exception` in server.py to specific exceptions
- [ ] Fix all 9 instances listed in AUDIT_REPORT.md section 7.1

### A3: Fix GUI Server Structural Issues (P0) — 8h
**File:** `gui/server.py`
- [ ] Move all late imports to top-level (8 instances)
- [ ] Refactor websocket_endpoint (95 lines → multiple methods)
- [ ] Add socket context managers for port checking
- [ ] Extract route handlers into `gui/api/` module (chat.py, models.py, sessions.py, settings.py)
- [ ] Add proper error boundaries per endpoint
- [ ] Add rate limiting hardening

### A4: Mark OnnxEngine as Not Implemented (P0) — 1h
**File:** `llm/onnx_engine.py`
- [ ] Add clear `# NOT IMPLEMENTED — placeholder for future ONNX Runtime GenAI integration` header
- [ ] Make all methods raise `NotImplementedError` with clear messages
- [ ] Update CONTEXT.md and task.md to reflect actual status

### A5: Remove Sub-Projects — ✅ Done
- [x] Moved `leworldmodel/` to `D:/Project/CustomLLM/`
- [x] Moved `mythos-server/` to `D:/Project/CustomLLM/`

---

## PHASE B: CORE REFACTORING (Days 3-5)

**Goal:** Fix all P1 issues — make the core architecture solid.

### B1: Refactor LocalEngine (P1) — 6h
**File:** `llm/local_engine.py` (839 lines)
- [ ] Split into modules: `core/model_loader.py`, `core/inference.py`, `core/agent_protocol.py`
- [ ] Add context manager (`__enter__`/`__exit__`) for model lifecycle
- [ ] Replace busy-wait with `threading.Event` for model loading
- [ ] Extract hardcoded defaults to config
- [ ] Add graceful error recovery in generate()
- [ ] Add tests

### B2: Refactor AgentLoop.run() (P1) — 4h
**File:** `core/agent.py` (150+ line method)
- [ ] Extract `_step()` — single iteration of the agent loop
- [ ] Extract `_execute_tool()` — already partially done, complete the extraction
- [ ] Extract `_check_permission()` — already referenced, make standalone
- [ ] Fix late imports (TaskGraph, ReflectionEngine) using TYPE_CHECKING
- [ ] Fix global mutable state in `_tool_map` and `_trace_buffer`
- [ ] Add tests for each extracted method

### B3: Refactor Sandbox (P1) — 3h
**File:** `core/sandbox.py`
- [ ] Add non-Docker fallback (direct subprocess with sandboxing)
- [ ] Ensure Docker containers are always cleaned up (`try/finally`)
- [ ] Add platform detection for sandbox method selection
- [ ] Add tests

### B4: Fix Planner/Executor (P1) — 3h
**Files:** `core/planner.py`, `core/executor.py`
- [ ] Replace `shell=True` with `subprocess.run(list_args)`
- [ ] Add timeouts to all subprocess calls
- [ ] Add error propagation for tool failures
- [ ] Add tests

### B5: Refactor CLI App (P1) — 6h
**File:** `cli/app.py` + mixins
- [ ] Separate state into `AppState` dataclass (UI, session, config)
- [ ] Add non-TTY fallback for pipe/redirect mode
- [ ] Add proper signal handling
- [ ] Add tests for command parsing and event handling
- [ ] Optimize Textual startup (lazy-load panels)
- [ ] Add `--lightweight` flag for streaming-only mode

### B6: Fix Tool Security & Deduplication (P1) — 3h
**Files:** `tools/code_edit.py`, `tools/file_ops.py`, `tools/shell.py`
- [ ] Fix `re.search()` None crash in code_edit.py
- [ ] Extract shared FileUtils helper from file_ops.py + code_edit.py
- [ ] Add AST-based matching as fallback for Python files
- [ ] Add tests

---

## PHASE C: COMPLETENESS (Days 5-8)

**Goal:** Implement missing P2 components and achieve comprehensive test coverage.

### C1: Implement Missing Phase 9 Components — 15h
- [ ] `core/task_graph.py` — Hierarchical task DAG (~4h)
- [ ] `core/nla_telemetry.py` — Reasoning telemetry (~3h)
- [ ] `core/debate.py` — Multi-agent debate consensus (~4h)
- [ ] `core/devops.py` — Local CI pipeline (~4h)

### C2: Implement Smart Router — 2h
**File:** `llm/runtime_manager.py`
- [ ] Add latency tracking per provider
- [ ] Add task complexity-based routing
- [ ] Add fallback chain configuration

### C3: Add Tests for Untested Modules — 16h
- [ ] `memory/` — 5 files, ~3h
- [ ] `session/` — 3 files, ~2h
- [ ] `cli/` — 6 files, ~4h
- [ ] `mcp/` — 3 files, ~2h
- [ ] `skills/` — 2 files, ~1h
- [ ] `permissions/` — 2 files, ~1h
- [ ] `core/` remaining — 3 files, ~2h
- [ ] Improve existing tests (~1h)

### C4: Add Missing Provider Tests — 3h
- [ ] Test all 9 cloud providers
- [ ] Parameterize duplicate tests

### C5: Add First-Run Setup Wizard — 4h
**Files:** `cli/wizard.py` (new), `core/config.py`
- [ ] Hardware detection
- [ ] Model recommendation and download
- [ ] Permission mode selection
- [ ] Memory mode selection
- [ ] Error handling mode selection
- [ ] Config persistence

---

## PHASE D: POLISH (Days 8-10)

**Goal:** Production-quality documentation, install, CI/CD.

### D1: Documentation Suite — 8h
- [ ] `docs/ARCHITECTURE.md` — System architecture, data flow, module map
- [ ] `docs/API.md` — REST + WebSocket + MCP API reference
- [ ] `docs/CONTRIBUTING.md` — Contribution guidelines
- [ ] `docs/SECURITY.md` — Security policy
- [ ] `docs/examples/` — Usage examples and tutorials
- [ ] Update `README.md` — Polish, badges, installation options
- [ ] Update `docs/CONTEXT.md` — Accurate project state

### D2: Install Scripts — 4h
- [ ] `install.ps1` — Windows PowerShell installer (handles Python, venv, deps, config)
- [ ] `install.sh` — Linux/macOS bash installer
- [ ] Verify `pip install -e .` works cleanly
- [ ] Verify `pip install nexus-agent` (eventual PyPI publish)

### D3: CI/CD — 4h
- [ ] `.github/workflows/test.yml` — Run tests on every push
- [ ] `.github/workflows/lint.yml` — Run ruff + mypy on every push
- [ ] `.github/workflows/publish.yml` — Publish to PyPI on tag

### D4: Update Docs/CONTEXT.md — 2h
- [ ] Accurate file-by-file status
- [ ] Accurate phase completion percentages
- [ ] Updated continuation prompt for other AI agents

---

## POST-LAUNCH (Future Phases)

| Phase | Focus | When |
|-------|-------|------|
| E | Linux port | After Windows stable |
| F | Web GUI PWA | After CLI complete |
| G | iOS Safari GUI | After Web GUI |
| H | Native iOS app | After Web GUI stable |
| I | Native desktop apps (Tauri) | After all platforms stable |
| J | Python plugin system | After skills + MCP |
| K | Multi-user / cloud sync | v2.0 |

---

## EFFORT SUMMARY

| Phase | Hours | Risk | Deliverables |
|-------|-------|------|-------------|
| A: Critical Fixes | ~14h | Low | Secure shell, fixed server, vaporware removed |
| B: Core Refactoring | ~25h | Medium | Solid architecture, well-structured modules |
| C: Completeness | ~40h | Medium | Missing features, comprehensive tests |
| D: Polish | ~18h | Low | Docs, install scripts, CI/CD |
| **Total** | **~97h** | | **Production-ready v1.0** |
