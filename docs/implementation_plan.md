# Phase 9 — Full-Spectrum Agent Architecture (All 18 Categories)

Comprehensive plan to implement **all 57 actionable feature gaps** identified by the [full-spectrum audit](file:///C:/Users/ssjag/.gemini/antigravity-ide/brain/908aad15-4430-4265-b37b-f1971ab0191e/full_spectrum_audit.md) across all 18 agentic CLI feature categories.

**Current state:** 94/196 subfeatures implemented (48%), 40 partial, 57 missing, 5 not feasible.  
**Target state:** 151/196 subfeatures implemented (77%), with all partial items completed.

---

## Already Completed (during this session)

| File | Status | Description |
|:---|:---:|:---|
| [self_heal.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/self_heal.py) | ✅ Done | Self-healing execution engine with retry orchestration, error classification, exponential backoff, diagnosis prompts |
| [reflection.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/reflection.py) | ✅ Done | Generator-Critic reflection loops with structured scoring, self-correction chains, heuristic fallback |

---

## Phase 9A — Core Agent Intelligence (High Impact)

Covers gaps from **#1 Foundational Architecture**, **#16 Self-Improvement**, **#9 Multi-Agent**.

### [NEW] [task_graph.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/task_graph.py)
**Audit gaps covered:** Recursive decomposition, Hierarchical task graphs, Goal refinement, Task memory
- `TaskNode` dataclass: `id`, `title`, `description`, `status` (pending/running/completed/failed/blocked), `parent_id`, `children`, `dependencies`, `result`
- `TaskGraph` class:
  - `decompose(goal) → TaskNode` — LLM-driven recursive goal decomposition (max depth 3)
  - `get_ready_tasks()` — Returns tasks whose dependencies are all satisfied
  - `execute_next() → Iterator[AgentEvent]` — Picks next ready task, runs agent loop, updates status
  - `get_progress() → dict` — Percentage complete, counts by status
  - `to_markdown()` — Renders task tree as checklist
  - `to_mermaid()` — Generates Mermaid DAG diagram
- Persists to `.nexus-agent/tasks/{session_id}.json`

### [NEW] [nla_telemetry.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/nla_telemetry.py)
**Audit gaps covered:** NLA reasoning logs, Error pattern learning, Strategy refinement, Execution retrospectives
- `NLATelemetry` class:
  - `log_iteration()` — After each agent iteration, generates structured reasoning trace entry
  - Fields: `thought_process`, `strategy_selected`, `tools_considered`, `confidence_score`, `alternative_paths`, `learning_signal`
  - JSONL output to `.nexus-agent/nla_logs/nla_{session_id}.jsonl`
  - `generate_session_summary()` — Human-readable Markdown reasoning summary
  - `export_training_pairs()` — Extract `(input, ideal_output)` pairs from successful sessions
  - `get_error_patterns()` — Analyze logged errors for recurring patterns

### [NEW] [debate.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/debate.py)
**Audit gaps covered:** Debate agents, Multi-agent consensus, Critic agents, Confidence scoring, Multi-agent voting, Reviewer agent, Security auditor
- `ReviewerPersona` dataclass: `name`, `focus_area`, `system_prompt`
- Built-in personas: `SecurityReviewer`, `PerformanceReviewer`, `CorrectnessReviewer`, `StyleReviewer`
- `DebateEngine` class:
  - `review(code_changes, context)` — Each reviewer independently critiques using different system prompts
  - `judge(reviews)` — Aggregates reviews, resolves conflicts, produces `DebateVerdict`
  - `DebateVerdict` dataclass: per-reviewer scores, aggregated issues, consensus score, final recommendation
  - Convergence: max 3 rounds or all reviewers approve

---

## Phase 9B — Verification & Quality (High Impact)

Covers gaps from **#6 Testing & Validation**, **#12 Software Engineering Intelligence**, **#13 DevOps**.

### [NEW] [devops.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/devops.py)
**Audit gaps covered:** CI/CD integration, Static analysis integration, Autonomous testing, Patch failing code, Retry until passing, Stack trace analysis, Vulnerability scanning, Secret detection, Dependency auditing
- `VerificationPipeline` class:
  - `detect_test_framework()` — Scans workspace for `pytest.ini`, `setup.cfg[tool:pytest]`, `package.json[scripts.test]`, `Cargo.toml`, `go.mod`
  - `run_tests()` — Executes detected test suite, parses exit code and output
  - `run_linters()` — Runs `ruff check` / `mypy` / `eslint` if configured
  - `parse_traceback(stderr)` — Regex parser extracting file, line, error from Python/JS/Go tracebacks
  - `scan_secrets()` — Regex scanner for API keys, tokens, passwords in source files
  - `scan_vulnerabilities()` — Runs `pip audit` / `npm audit` and parses output
  - `create_safety_branch()` — Creates git checkpoint branch before changes
  - `run_full_pipeline()` — Orchestrates: snapshot → apply → verify → report
  - Integrates with `SelfHealingExecutor` for retry-until-passing on test failures

---

## Phase 9C — Git & DevOps Intelligence (Medium Impact, Low Effort)

Covers gaps from **#5 Git & Version Control**, **#13 DevOps & Infrastructure**.

### [MODIFY] [git_ops.py](file:///D:/Project/nexus-agent/src/nexus_agent/tools/git_ops.py)
**Audit gaps covered:** Contextual commit messages, Conventional commits, Change summarization, PR generation, PR reviews, CI log analysis
- Add `SmartCommitTool` class:
  - `generate_message()` — Runs `git diff --staged`, feeds to LLM, returns conventional commit message (`feat:`, `fix:`, `docs:`, etc.)
- Add `PRGeneratorTool` class:
  - `generate_pr()` — Aggregates commit log + diff summary → LLM generates PR title + body
- Add `CIAnalyzerTool` class:
  - `analyze_log(log_text)` — Parses CI output (GitHub Actions, pytest output) and diagnoses failures

### [MODIFY] [shell.py](file:///D:/Project/nexus-agent/src/nexus_agent/tools/shell.py)
**Audit gaps covered:** Docker orchestration, Terraform generation, Cloud deployment, Log analysis
- Add convenience wrappers for `docker`, `kubectl`, `terraform` that validate availability before execution

---

## Phase 9D — Advanced Codebase Understanding (Medium Impact, Medium Effort)

Covers gaps from **#2 Codebase Understanding Systems**.

### [NEW] [code_intel.py](file:///D:/Project/nexus-agent/src/nexus_agent/tools/code_intel.py)
**Audit gaps covered:** Dependency graphs, Import tracing, Call graph generation, Hierarchical summarization, Rename propagation
- `ImportGraphTool` class:
  - `build_graph(workspace)` — Parses Python `import` / `from...import` and JS `import`/`require` statements via regex
  - Returns adjacency list of module dependencies
  - `find_dependents(module)` — "What breaks if I modify this?"
- `CallGraphTool` class:
  - `build_call_graph(file)` — AST visitor tracking `ast.Call` nodes → maps caller→callee
  - `trace_function(name)` — "Where is this function used?"
- `RenameTool` class:
  - `rename_symbol(old, new, scope)` — AST-based find-all-references + batch rename across files

---

## Phase 9E — Model & Runtime Intelligence (Lower Impact, Low Effort)

Covers gaps from **#15 Model Orchestration**.

### [MODIFY] [runtime_manager.py](file:///D:/Project/nexus-agent/src/nexus_agent/llm/runtime_manager.py)
**Audit gaps covered:** Cost-aware routing, Latency-aware routing, Cloud fallback chain
- Add `SmartRouter` class:
  - `_response_times: dict[str, float]` — Track average response times per provider
  - `select_provider(task_complexity)` — Route simple tasks to local/fast models, complex to cloud
  - `fallback_chain` — Ordered list of providers to try on failure (local → ollama → cloud)
  - `update_latency(provider, duration)` — Online latency tracking

---

## Phase 9F — CLI & GUI Integration

Wires all new components into user-facing interfaces.

### [MODIFY] [agent.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/agent.py)
- Import `SelfHealingExecutor` — replace direct `_execute_tool()` with healing wrapper
- Import `ReflectionEngine` — add post-generation critique when `effort_level == "high"`
- Import `NLATelemetry` — call `log_iteration()` after each loop iteration
- Add `_run_reflection_pass()` method

### [MODIFY] [orchestrator.py](file:///D:/Project/nexus-agent/src/nexus_agent/core/orchestrator.py)
- Import `TaskGraph` — use for goal decomposition in `run_autonomous()`
- Import `DebateEngine` — post-execution code verification
- Import `VerificationPipeline` — test-driven validation after executor finishes
- Add `run_autonomous(goal)` method: decompose → plan each → execute each → verify → debate → report

### [MODIFY] [app.py](file:///D:/Project/nexus-agent/src/nexus_agent/cli/app.py)
- `/reflect` — Trigger manual reflection on last output
- `/task` — Display current task graph progress
- `/debate` — Trigger multi-agent review of pending changes
- `/verify` — Run verification pipeline manually
- `/nla` — View NLA reasoning log summary
- `/commit` — Generate smart commit message from staged changes
- Status bar: show task graph progress percentage

### [MODIFY] [server.py](file:///D:/Project/nexus-agent/src/nexus_agent/gui/server.py)
- `GET /api/tasks` — Current task graph state
- `GET /api/nla/{session_id}` — NLA reasoning logs
- `POST /api/debate` — Trigger debate verification
- `POST /api/verify` — Trigger verification pipeline
- `POST /api/commit` — Generate smart commit message

### [MODIFY] [tests/test_advanced.py](file:///D:/Project/nexus-agent/tests/test_advanced.py)
- `test_self_healing_retry_loop` — Verify retry with error diagnosis
- `test_reflection_critic_loop` — Verify critique scoring and feedback
- `test_task_graph_decomposition` — Verify goal→subtask DAG
- `test_nla_telemetry_logging` — Verify JSONL log generation and format
- `test_debate_consensus` — Verify multi-reviewer consensus protocol
- `test_verification_pipeline` — Verify test framework auto-detection
- `test_failure_classification` — Verify error classification heuristics
- `test_code_intel_import_graph` — Verify import graph building

---

## Open Questions

> [!IMPORTANT]
> **Execution order**: The plan is structured in priority order (9A→9B→9C→9D→9E→9F). Should all phases be implemented in one session, or would you prefer to implement and test incrementally?

> [!NOTE]
> **Dependency graph scope**: The import/call graph tools in Phase 9D use regex and `ast` module parsing. For full-accuracy cross-language support (TypeScript, Rust, Go), `tree-sitter` (already in `pyproject.toml`) could be leveraged. Should we add tree-sitter grammars for additional languages?

---

## Verification Plan

### Automated Tests
```bash
python -m unittest discover -s tests
```

### Manual Verification
1. `nexus chat` → type `/task <complex goal>` to see task decomposition
2. `nexus chat` → type `/reflect` after an agent response to see critique
3. `nexus chat` → type `/verify` to run test/lint pipeline
4. `nexus chat` → type `/debate` to trigger multi-agent code review
5. `nexus chat` → type `/nla` to view reasoning logs
6. `nexus chat` → type `/commit` to generate smart commit message
