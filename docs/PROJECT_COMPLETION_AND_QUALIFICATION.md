# NexusAgent Project Completion, Deployment, and Qualification Guide

> Last reviewed: 2026-10-09  
> Canonical version: 0.3.0-alpha.5  
> Canonical integration branch: main  
> Qualification posture: alpha hardening; not a 1.0 release

This is the working engineering contract for taking NexusAgent from the current alpha platform to a defensible release. It defines what must be implemented or hardened, where changes belong, how to test them, how to package and deploy them, what evidence qualifies a change, and which gates block promotion. It supersedes dated phase estimates in older planning notes; it does not claim every future milestone is already implemented.

## 1. Definition of complete

NexusAgent is a local-first agentic development and research workbench with a shared Python runtime, CLI/TUI, FastAPI web console, native Rust CLI, native desktop client, provider integrations, local model backends, tools, memory, skills, MCP and multi-agent orchestration.

A release tier is complete only when:

1. A user can install it using the documented path on every claimed platform and start a supported workflow without hidden developer setup.
2. Every documented user-facing operation has defined input, output and error behavior plus automated tests. Unsupported operations fail clearly instead of returning success-shaped placeholders.
3. CLI, web, team runtime, MCP and native clients share the same semantics for permissions, cancellation, error reporting, configuration, sessions and artifacts where they expose equivalent operations.
4. The agent loop, scheduler, providers, persistence and tools handle retries, cancellation, timeouts, resource limits and partial failure deterministically.
5. Every state-changing tool action is authorized at the actual action boundary. Filesystem, network, subprocess, credential and data-export boundaries are tested against adversarial inputs.
6. Persistent schemas have migrations, integrity checks, resource bounds and documented backup/recovery procedures.
7. The complete supported test matrix, formatting, lint, type-check scope, native checks, version contract and security gates pass on the exact candidate commit.
8. Release artifacts can be installed and smoke-tested in clean environments; tag, packages, binaries and release notes agree on one version and source commit.
9. Operational limitations and known risks are explicit. Green workflows are necessary evidence, not a substitute for product correctness or repository governance.

A module existing, a mock-only test, a historical audit report, a queued workflow or a successful subset of tests is not proof of completion.

## 2. Baseline and known external governance work

The latest repository snapshot observed on 2026-10-09 was version 0.3.0-alpha.5 at main commit f338d8246dfa1d39a9a77cbc33e0996b8ef26432. CI run 37918696905 and Security run 37918696726 completed successfully for that commit. Re-query live refs and workflow runs before relying on this snapshot for any later promotion.

External GitHub settings remain a separate gate:

- main is the intended canonical integration branch, but GitHub still reports master as the repository default.
- main is not protected in GitHub settings. The checked-in policy in .github/BRANCH_PROTECTION.md is a specification, not proof that GitHub enforces it.
- Issue #326 tracks the administrator-only default-branch and branch-protection changes. A repository administrator must set main as default and apply the documented protections/ruleset.
- Never force-push or rewrite history to make branches appear synchronized. Keep master fast-forwarded only while it remains the default; after the administrator changes the default, explicitly decide whether to retain or retire the compatibility branch.

The dependency audit contains one documented temporary exception for PYSEC-2026-2447 affecting diskcache versions pulled transitively by llama-cpp-python. This is not a general audit waiver. Reassess the exception when upstream fixes the issue, the dependency graph changes, or NexusAgent begins using LlamaCache/DiskCache directly.

## 3. Architecture and ownership map

Implement behavior in the owning layer and reuse it across surfaces. Do not implement a second scheduler or permission system inside the UI.

| Layer | Main ownership | Invariants |
|---|---|---|
| User surfaces | src/nexus_agent/cli/, src/nexus_agent/gui/, nexus-rs/, nexus-desktop/ | Surfaces call shared contracts; UI state is not hidden business logic. |
| Agent execution | core/agent.py, core/orchestrator.py, core/planner.py, core/executor.py | Every tool call has explicit state, bounded execution, observable failure and an authorization decision before side effects. |
| Tool adapters | src/nexus_agent/tools/ | Each tool declares inputs, permissions/capabilities, side effects, limits, error behavior and tests. |
| Multi-agent runtime | src/nexus_agent/team/ | Scheduling is dependency-aware, bounded, cancellable and recoverable; worker permissions hold in every construction path. |
| Provider layer | src/nexus_agent/llm/base.py, llm/providers/, llm/runtime_manager.py | Provider capabilities and errors are normalized; fallback does not hide permission errors or change model identity silently. |
| Research evidence | src/nexus_agent/research/ | Sources are authoritative snapshots, claims link to evidence, stale verification cannot pass current coverage, and quality results are reproducible. |
| Persistence/security | src/nexus_agent/storage/, memory/, session/, auth/, permissions/ | One canonical storage layout; migrations are tested; credentials are separate; path, network and identity boundaries fail closed. |
| HTTP/MCP contracts | web_routes.py files and src/nexus_agent/mcp/ | Validation, access policy, authorization, status codes and output schemas are explicit and tested. |
| Package/release | pyproject.toml, VERSION, scripts/, .github/workflows/ | Versions agree; outputs are traceable to a tested tag commit; no release uses an unqualified tree. |

Architecture and user contracts are documented in docs/ARCHITECTURE.md, docs/API.md, docs/MULTI_AGENT_PLATFORM.md, docs/ORCHESTRATION.md, docs/PROVIDERS.md, docs/STORAGE_AND_GOVERNANCE.md and docs/VERSIONING.md. Update the owning document whenever behavior or a public contract changes.

## 4. Implementation program and exit criteria

Work in this order. A later phase does not excuse a failed earlier gate. Do not add speculative features while correctness, security, compatibility or release evidence is unresolved.

### Phase 0 — Governance and reliable engineering loop

Implement:
- Set main as the repository default through GitHub administration.
- Protect main with PR review, Code Owner review, stale-approval dismissal, required CI / Required and Security / Required, up-to-date branch requirement, resolved conversations, no force-push/delete and administrator enforcement.
- Keep CODEOWNERS and .github/BRANCH_PROTECTION.md aligned with real settings.
- Ensure every PR gets CI and Security. Do not run privileged write-token workflows on untrusted PR code.
- Preserve test diagnostics on failure and make aggregate gates fail when a required child job fails or is unexpectedly skipped.
- Pin third-party GitHub Actions to immutable commit SHAs as a security-hardening task, with dependency updates reviewed through PRs.

Implementation:
- Use .github/workflows/ci.yml and security.yml for checks, .github/BRANCH_PROTECTION.md for policy and issue #326 for GitHub-side administration.
- If the available integration cannot change repository settings, record the exact administrator action. Never label documented policy as enforced policy.

Tests/qualification:
- CI and Security run on PRs and default-branch pushes.
- Aggregate jobs fail if a required child gate fails or is unexpectedly skipped.
- Version/policy scripts reject invalid fixture inputs.
- Verify GitHub branch metadata and rulesets after administrative changes.

Exit gate:
- main is default and protected in GitHub itself.
- CI / Required and Security / Required are required checks.
- Recent main and PR runs are green on the exact commits proposed for promotion.

### Phase 1 — Explicit public contracts

Implement:
- Versioned contracts for CLI commands, HTTP endpoints, MCP tools, provider configuration, serialized events, team lifecycle, artifacts and persistence formats.
- Normalized error categories: invalid input, denied action, provider unavailable, timeout/cancel, dependency failure, corrupt persisted state and internal failure.
- Compatibility rules for configuration fields, event schemas, public function arguments and storage migrations.
- One source of truth for defaults and normalization, avoiding drift between Python, CLI and native clients.

How:
1. Inspect routes, Click commands, Pydantic models, LLMProvider, ACP/JSON-RPC messages, TeamConfig and storage schemas.
2. Add contract tests against real handlers/adapters before refactoring.
3. Extract shared validation/serialization only where callers currently diverge.
4. Preserve alpha compatibility unless a breaking change is intentional; document migrations and bump the prerelease according to docs/VERSIONING.md.
5. Keep user-visible errors actionable without exposing secrets, absolute local paths or remote stack traces.

Tests:
- Success/failure schema contracts.
- Missing, extra, oversized and wrong-type inputs.
- Current config plus supported prior persisted formats.
- CLI, web and native tests asserting equivalent semantics for equivalent operations.

Exit gate:
- No advertised operation relies on undocumented behavior or raw internal exception text.
- docs/API.md matches the live implementation.

### Phase 2 — Agent-loop correctness and controlled tool execution

Implement:
- Explicit lifecycle states for reasoning, tool execution, approval, cancellation, retry and completion.
- Per-tool validation, deadlines, cancellation checks, output limits and normalized results.
- Permission decisions based on the actual action and arguments. Distinguish read-only subcommands from mutation subcommands.
- Retry only errors classified as transient; do not retry authorization denials, invalid input or user cancellation.
- Useful audit/telemetry for selected tool, permission decision, duration and failure, without secrets.

How:
1. Trace every AgentLoop construction path: team worker, research round, native backend and web-triggered work.
2. Route tool execution through the same authorization/result-normalization layer.
3. Use argument-vector subprocess calls with shell=False. On Windows, never invoke cmd.exe to parse untrusted commands. Refuse batch files/interpreters unless a dedicated reviewed policy exists.
4. Resolve paths and enforce workspace containment after symlink resolution and immediately before side effects.
5. Propagate cancellation to provider requests/subprocesses when supported.
6. Treat model output, agent profiles, MCP payloads and web content as untrusted.

Tests:
- Allowed/denied actions and invalid arguments.
- Adversarial command injection and path/symlink traversal on actual OS runners.
- Approval/provider/subprocess timeout, streaming cancellation and cleanup-after-failure.
- Property/fuzz tests for parsers and structured-data tools; assert no crash, unbounded output or workspace escape.
- Construct every AgentLoop variant and assert identical permission policy.
- Verify denied operations produce no process, filesystem, network or persistence side effect.

Exit gate:
- No secondary execution path bypasses permissions; every side effect is bounded and reported as completed, failed or cancelled.

### Phase 3 — Provider and local-model reliability

Implement:
- Shared provider capabilities for streaming, tool calling, multimodal requests, context limits, structured output and cancellation.
- Normalized provider errors with retryability and retry-after support.
- Explicit chosen provider/model attribution for each request and fallback.
- Credential add/list-metadata/validate/rotate/remove flows without displaying credentials.
- Local runtime health detection that degrades gracefully when optional engines, accelerators or drivers are absent.
- Safe model import/download/cache behavior where supported, including checksum, size and partial-file protection.

How:
1. Keep LLMProvider as the integration boundary.
2. Give every provider adapter a shared mocked-transport conformance suite.
3. Distinguish initialization failure, transport error, rate limit, invalid model, context overflow and refusal.
4. Apply bounded retries/backoff only when appropriate; honor retry-after and a total deadline.
5. Test optional dependencies absent, partially installed and incompatible.
6. Treat model files and provider responses as untrusted input.

Tests:
- Provider contract suite per implementation.
- Simulate 429, 5xx, timeout, malformed body, invalid credentials, reset and interrupted stream.
- Assert fallback ordering, budget and final error classification.
- CPU-only plus platform-specific accelerator smoke tests where claimed.
- Assert keys never enter logs, exceptions, telemetry or saved sessions.

Exit gate:
- Providers pass shared contracts, document capability differences and degrade predictably.

### Phase 4 — Team orchestration and lifecycle

Implement:
- Typed plans, stable worker IDs, explicit dependencies, cycle/unknown-dependency failure, max parallelism and total resource/deadline budgets.
- Persistent queued/running/completed/failed/cancelled/needs-review states with legal transitions tested.
- Pause/resume/stop semantics during idle, active tool, provider wait and worker failure.
- Per-worker provider/model assignment with deterministic fallback and persisted attribution.
- Worker-local tool catalog and permission policy preserved in ordinary and research paths.
- Collision-resistant job/team IDs, safe retry/resume behavior and idempotent duplicate-request handling.
- Team events/messages that cannot smuggle trusted executable instructions from unverified workers.

How:
1. Keep scheduler behavior in team/runtime.py, models in team/models.py and durable lifecycle state in team/store.py.
2. Validate the full dependency graph before launching workers.
3. Make dependent-task failure policy explicit; never silently discard unresolved dependencies.
4. Put provider clients, research stores, scoped memory, temp directories and executors inside try/finally cleanup.
5. Bound plan size, worker count, iterations, message/result size, wall time and retained events.
6. Make every lifecycle transition idempotent or reject invalid repeats.

Tests:
- Independent tasks run concurrently up to the configured limit; dependencies do not start early.
- Unknown dependencies/cycles fail before worker execution.
- Pause/resume/stop at every lifecycle point.
- Duplicate requests cannot overwrite another job.
- Worker-local permissions survive ordinary, research and provider-fallback construction.
- Restart/recovery of state/artifacts and simulated partial store/provider failure.
- Randomized DAG stress tests for dependency violations and deadlocks.

Exit gate:
- State is coherent after failure, cancellation and restart, and workers cannot exceed authority/resource budgets.

### Phase 5 — Evidence-first research quality

Implement:
- Source records with URL, fetch time, content hash, title/provider, bounded snapshot and fetch/error status.
- Claims tied to evidence, exact quotes, verification identity/time and explicit verified/refuted/insufficient/stale states.
- Evidence mutation invalidates prior successful verification while retaining history for audit.
- Deterministic quality thresholds; missing citations/unverified claims never count as verified.
- Conflict resolution history; independent source counts must not be confused with deduplicated content hashes.
- Safe fetching with scheme/port restrictions, private-target checks, redirect-hop validation, response/time limits and DNS-rebinding-aware design.

How:
1. Keep migrations in research/store.py and tool behavior under research/.
2. Make multi-row operations atomic and use constraints for concurrent deduplication.
3. Distinguish content deduplication from independent-source count.
4. Mark old verdicts stale after evidence changes and require re-verification.
5. Do not trust worker-provided content when runtime source capture is required.
6. Validate each redirect target before following it, not only the final response URL.

Tests:
- Concurrent duplicate source inserts and concurrent claim/evidence updates.
- Exact/missing/partial/whitespace-modified quotes.
- Independent sources, duplicate content, stale verification and conflicts.
- Redirects to loopback/private/link-local/reserved IPv4/IPv6, malformed schemes, user-info URLs, loops and DNS errors.
- Oversized source, timeout, Unicode/control characters and prior schema migration.
- Full research workflow from question to source capture, verification and report, including forced failure.

Exit gate:
- Quality results are reproducible from stored records, stale evidence cannot pass, and provenance is auditable.

### Phase 6 — Persistence, sessions and recovery

Implement:
- One storage layout for workspace/user/runtime data.
- Versioned SQLite migrations, constraints, transactions, bounded timeouts and clear corruption/recovery behavior.
- Backup/restore for config, sessions, memory, teams, research, artifacts and user-authored agents/skills.
- Atomic file replacement and cleanup of incomplete writes.
- Retention/compaction for logs, events, checkpoints, embeddings, telemetry and artifacts.
- Explicit cross-process synchronization semantics.

How:
1. Derive paths through storage/layout.py rather than reimplementing path rules.
2. Test every migration against a fixture from the immediately preceding schema.
3. Never delete user data automatically during upgrade.
4. Use transactions for related DB changes and document the concurrency assumptions.
5. Distinguish disk-full, permission-denied, lock-timeout, corrupt database and schema mismatch errors.
6. State honestly whether the credential backend is encrypted or only access-restricted.

Tests:
- Upgrade supported schema fixtures and verify row preservation.
- Inject failures between writes and verify atomicity/recovery.
- Multiple processes concurrently accessing team/session stores.
- Read-only directory, locked DB, disk-full simulation and invalid rows.
- Backup/restore to a clean path including evidence provenance.
- Verify exports do not include private source content/secrets by default.

Exit gate:
- Upgrades are non-destructive and recovery is documented and tested.

### Phase 7 — Surface and integration parity

Implement:
- Shared semantics across CLI/TUI, FastAPI, MCP and native clients.
- API/WebSocket checks for origin/access policy, size limits, deadlines and cancellation.
- Stable streaming/event protocol for content, tool calls/results, approvals, task status and errors.
- Native/Python IPC health, bounded message sizes, orderly shutdown and dead-child recovery.
- Clear UI states for loading, streaming, approval, failure, cancellation and reconnect.

How:
1. Maintain one protocol contract and exercise each adapter through contract tests.
2. Separate protocol parsing from rendering.
3. Keep workspace APIs loopback-only unless a reviewed authenticated remote model exists.
4. Do not use Origin as sole authentication for remote access.
5. Version IPC and detect incompatible clients explicitly.
6. Keep long-running requests off the GUI event loop.

Tests:
- Shared contracts for HTTP and native IPC.
- Browser/WebSocket tests for approved/rejected origins, reconnect and mid-stream disconnect.
- Malformed JSON-RPC, EOF, child crash, timeout and shutdown tests.
- End-to-end chat, provider/model selection, tool approval, team lifecycle, artifact download and session resume.
- Keyboard/accessibility smoke tests and terminal restoration on exit/panic.
- Clean-environment client startup without a developer checkout.

Exit gate:
- Advertised cross-surface operations share one behavior definition and acceptance tests.

### Phase 8 — Installation, packaging and operations

Implement:
- A tested base install and documented optional extras by platform/feature.
- Correct package metadata, licenses, static assets, typing markers and entry points.
- CPU-first fallback and actual hardware build prerequisites.
- Traceable versioned builds, integrity checks, artifact names and provenance.
- Redacted operational logs, diagnostics and useful doctor output.
- Support matrix for OS, Python and native targets with explicit accelerator coverage.

How:
1. Run python -m build and python -m twine check dist/*; inspect wheel/sdist contents.
2. Install the built wheel in a clean environment, not just an editable checkout.
3. Build native CLI/desktop artifacts for every claimed target and smoke-test on native runners.
4. Ensure optional hardware SDKs are not required by normal installation.
5. Document uninstall/data retention; uninstalling the package must not delete user data unexpectedly.
6. Use prerelease channels and explicit release notes for rollout/rollback.

Tests:
- Install/uninstall from wheel and sdist.
- Verify nexus --version, nexus hardware and documented setup flow.
- CLI and local GUI startup in a clean VM/container.
- Native binaries print version/help, locate/start the Python runtime and exit cleanly.
- Check static assets, default config, migrations and entry points in the package.
- Record artifact hashes and verify provenance.

Exit gate:
- A user on a clean supported system can follow the install docs and run a documented workflow without a developer checkout.

### Phase 9 — Beta, release candidate and 1.0 stability

Beta readiness:
- No unresolved critical/high correctness or security defect.
- Feature scope frozen except release blockers.
- CLI/API/MCP/tool/provider/config/storage/team/native IPC contracts documented.
- Supported matrix matches actual tests and packaging.
- Upgrade, recovery, uninstall and rollback demonstrated.
- Risks and dependency exceptions have owners and revisiting conditions.

Release-candidate readiness:
- No planned features remain in scope.
- Only regression-tested fixes are accepted.
- The exact release workflow passes, including package validation and publication dry-run where available.
- Clean installs and upgrades pass on each supported OS.
- RC artifacts are exercised independently and traced to the tested commit.

1.0 readiness:
- Written public compatibility commitments exist.
- All public contracts and persistence/IPC migrations have stability/version policies.
- No unresolved Critical/High security issue; accepted Medium risks have owners and expiry.
- The diskcache audit exception is removed or formally re-justified using current advisory/dependency evidence.
- All required qualification checks pass on the exact tag candidate.
- Default branch/protections are active in GitHub itself.
- Documentation, support matrix, license, packaging and operational recovery instructions are complete.

## 5. Test strategy and evidence requirements

### Fast local gates

From the repository root, use Python 3.12 for closest parity with CI:

    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python -m pip check
    python -m compileall -q src
    python -m pytest tests/ -q --tb=short -W error::ResourceWarning
    python -m ruff check src/
    python -m ruff format --check src/
    python -m mypy --follow-imports=silent src/nexus_agent/team/runtime.py src/nexus_agent/team/models.py src/nexus_agent/team/quality.py src/nexus_agent/team/providers.py src/nexus_agent/research/store.py src/nexus_agent/storage/layout.py src/nexus_agent/agents/models.py
    python scripts/check_version.py
    cargo fmt --manifest-path nexus-rs/Cargo.toml -- --check
    cargo check --manifest-path nexus-rs/Cargo.toml
    cargo fmt --manifest-path nexus-desktop/Cargo.toml -- --check
    cargo check --manifest-path nexus-desktop/Cargo.toml

The enforced CI type-check command is the current critical-module list above. The release workflow may check a broader source scope; the intended end state is full supported-tree strict typing, not silently weakening release validation to the narrower list.

### Required test classes

- Unit tests for pure functions, parsers and normal/failure behavior.
- Contract tests for public request/result/error schemas.
- Integration tests using real store/orchestration/adapters while mocking external model/network boundaries.
- Persistence/migration tests across supported schema versions, concurrency and crash recovery.
- Security tests where denied actions have no side effects, covering injection, SSRF, path/symlink escape, data disclosure and oversized inputs.
- Cross-platform tests for filesystem, process, permissions and terminal behavior on actual OS runners.
- End-to-end user journeys from installation/setup through task completion and artifact/session recovery.
- Performance/resilience tests for representative workloads, startup, memory, max team size, output bounds and provider outage.
- Release smoke tests on artifacts installed in clean environments.

### Rules for meaningful tests

1. Every bug fix adds a regression test that fails before the fix.
2. Security tests inspect side effects/call counts, not only error text.
3. Avoid sleep-only synchronization; use barriers, events, fake clocks or explicit deadlines.
4. Use unique temporary workspaces and cleanup on failure. Tests must not touch a developer's home/workspace.
5. Mock external boundaries, not the state transition being tested.
6. Test success and clear failure behavior.
7. Mark hardware/provider tests explicitly; core qualification remains deterministic.
8. Preserve full test output as CI artifact on failure.
9. Skipped tests are not passes for a claimed feature unless an allowed platform limitation and alternate test are documented.
10. Re-test every affected caller when changing shared models, signatures, permissions or persistence contracts.

## 6. CI, Security and branch acceptance

The live workflow and run result are authoritative, not a badge alone.

CI qualifies:
- Python 3.10, 3.11, 3.12 and 3.13 on Ubuntu, Windows and macOS.
- Editable installation, dependency consistency and Python package compilation.
- Full pytest suite and retained canonical test evidence.
- Ruff lint and formatting.
- Strict MyPy for explicitly declared critical runtime/evidence modules, plus a tracked path toward full-tree coverage.
- Rust formatting/compilation for nexus-rs and nexus-desktop on supported runners.
- Version synchronization.
- Audit-evidence generation only after successful canonical tests.

Security qualifies:
- CodeQL.
- Python dependency audit with only documented, time-bounded exceptions.
- Dependency Review when repository settings make it available.
- An aggregate gate that fails on failed required security jobs.
- Secret handling, least-privilege workflow permissions and no privileged execution of untrusted PR content.

Before merge:
1. PR is based on current main and has no conflicts.
2. CI / Required and Security / Required pass on the exact current PR head.
3. Review and Code Owner requirements are met.
4. Dependencies have a justified need, license check, compatibility review and security posture.
5. Manifests/lockfiles are synchronized.
6. Docs/changelog describe observable behavior only.
7. No tests were disabled, security gates removed or assertions weakened just to get a green result.
8. Post-merge main CI/Security pass on the merge commit.

Queued, cancelled, skipped or stale-head runs are not passes.

## 7. Versioning, packaging and deployment

The repository-root VERSION file is canonical. scripts/check_version.py is authoritative. Never update only one manifest.

### Development setup

    git clone https://github.com/shreyashjagtap157/nexus-agent.git
    cd nexus-agent
    python -m venv .venv
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python -m pip check
    nexus --version
    nexus hardware

Activate the environment between creating it and installing. Install optional extras only for features being tested; accelerator packages can be large and platform-specific.

### Local smoke testing

    nexus chat
    nexus gui
    cargo run --manifest-path nexus-rs/Cargo.toml -- --help
    cargo run --manifest-path nexus-desktop/Cargo.toml

Use a local model or test provider as documented. Never commit a provider key. Keep web endpoints local unless a remote-authentication design has been reviewed.

### Prerelease/release

1. Preview the next version with scripts/set_version.py and its dry-run option.
2. Apply the bump, update CHANGELOG.md and any migration notes, then run scripts/check_version.py.
3. Run applicable local gates and open a PR.
4. Merge only after current-head CI/Security and reviews pass.
5. Verify post-merge workflows and record their URLs plus commit SHA.
6. Build and install the wheel/sdist in a clean environment; inspect package metadata and contents.
7. Tag only a commit already in main history with v followed by the exact canonical version. Never reuse or retarget a published tag.
8. Allow .github/workflows/release.yml to run the release gate, Python package build, native CLI/desktop builds, provenance attestation and publication.
9. Verify PyPI and GitHub Release assets, version, platform names, release notes and provenance.
10. Install the published package and smoke-test documented flows; record platform limits.
11. If any artifact fails, stop promotion and publish a corrected new version/tag instead of mutating an existing release.

### Deployment model

NexusAgent is primarily a local-first installed application. Deployment means distributing the Python package and native artifacts and configuring them on a workstation. A shared/remote server is a different security model and needs authentication, authorization, trusted-proxy configuration, tenant isolation, secrets management, rate/size limits, audit retention, backup/restore drills and a separate threat model. Loopback restrictions are not remote authentication.

### Rollback and recovery

- Preserve the prior artifact/package and release notes.
- Never delete user data automatically during rollback.
- Back up configuration, sessions, memory, teams, research databases, artifacts and user-authored agents/skills before migration.
- Test whether the prior version can read the preserved state; otherwise provide an export/migration/restore path before shipping.
- Revoke and rotate exposed credentials immediately; deleting a file does not remove secrets from Git history.
- Replace compromised releases with a new immutable release and clear advisory; never rewrite published tags.

## 8. Observability, support and maintenance

Maintain:
- Correlation IDs across request, team, worker, provider call and tool execution.
- Redacted logs for permission decisions, provider errors, timeouts, resource exhaustion and database failures.
- Health/readiness statuses distinguishing runtime available, model loaded, provider reachable and optional feature unavailable.
- Bounded logs/events and retention policy.
- Diagnostic output that excludes keys, credential stores and private source contents by default.
- Actionable doctor output for versions, optional dependency availability, model/workspace access and provider readiness.
- Support matrix tied to actual test coverage.
- Dependency-update triage: security fix, compatible update, risky major update or documented deferral with owner and expiry.

Measure startup, time to first token, provider latency/failures, tool duration/output bytes, approval/denial counts, team queue delay, research source failures/coverage, database errors and resource consumption. Do not log secrets/private source contents. Set performance budgets from measurements on supported hardware rather than inventing a universal latency promise.

## 9. Release qualification checklist

For every candidate, record the commit SHA and links to actual runs.

### Source and contracts
- [ ] Candidate is on main history and based on the intended release line.
- [ ] VERSION, Python package, Cargo manifests/lock entries and default configs match.
- [ ] CLI/API/MCP/provider/storage/native protocol changes are documented with migrations.
- [ ] Changelog describes actual merged changes.
- [ ] No temporary automation, secrets or generated junk remains.

### Correctness and compatibility
- [ ] Full supported test matrix passes.
- [ ] Ruff check and format pass.
- [ ] Declared MyPy checks pass and no new type debt is untracked.
- [ ] Both Rust projects format and compile on supported OS runners.
- [ ] Install, CLI start, GUI start, native start, normal task, denied tool, timeout/cancel and shutdown are smoke-tested.
- [ ] Provider fallback, research verification, migration, session resume and artifact recovery have integration coverage.
- [ ] Clean-environment upgrade and rollback have been exercised.

### Security and governance
- [ ] CodeQL passes.
- [ ] Dependency audit and Dependency Review pass, or every exception names an advisory, rationale, owner, revisit trigger and compensating control.
- [ ] SSRF, path/symlink escape, command injection, authorization bypass, secret disclosure and oversized inputs have regression tests.
- [ ] No unresolved Critical/High finding remains; accepted risks have owners and dates.
- [ ] main is default and protected in GitHub; required checks and reviews are enforced.
- [ ] Release secrets/environments use least privilege.

### Artifact and deployment
- [ ] Build, metadata validation and provenance complete.
- [ ] Wheel/sdist and native platform assets are present.
- [ ] Artifact version equals tag and VERSION.
- [ ] Fresh installs pass on each claimed platform.
- [ ] Upgrade/rollback and backup requirements are published.
- [ ] GitHub Release notes, platform support, known limits and security contact are correct.
- [ ] Post-publication smoke checks pass and evidence is retained.

A checklist item is complete only when its evidence can be independently inspected.

## 10. Prioritized backlog

P0 — release blocking:
1. Set main as the GitHub default and apply .github/BRANCH_PROTECTION.md protections (administrator action tracked in issue #326).
2. Keep main CI/Security green with evidence tied to the exact candidate commit.
3. Remove or formally renew the diskcache advisory exception after reviewing current upstream and dependency evidence.
4. Reconcile the difference between CI's critical-module MyPy list and the release workflow's broader type-check invocation; expand normal CI coverage so type failures do not surprise maintainers at tag time.
5. Correct stale docs/CONTEXT.md, docs/ROADMAP.md and docs/implementation_plan.md so they describe alpha.5 and do not claim production-ready v1.0 or unfinished features already implemented.

P1 — next engineering cycle:
1. Full-tree typing plan with measurable module coverage and no blanket ignores.
2. Cross-surface end-to-end smoke suite for CLI, GUI/WebSocket, MCP, native CLI and desktop.
3. SQLite migration, backup/restore and crash-recovery qualification.
4. Provider adapter conformance for timeout, retry, cancellation, context limits and fallback identity.
5. Performance/load baselines for max team size, output/event limits and provider outage recovery.
6. Package installation and native binary smoke tests in clean environments.
7. Structured/redacted diagnostics, doctor output and a support matrix.

P2 — after correctness stabilizes:
1. UX/accessibility and setup friction.
2. Measured performance optimization/resource budgets.
3. Additional providers/backends/tools only when they solve a documented need and include parity/security tests.
4. Remote/shared deployment only after a separate authentication/isolation/operations design is reviewed.

## 11. Work-item execution and handoff

For each work item:
1. Inspect live main, architecture/contracts, tests, workflows and latest CI/Security.
2. Define observable behavior and invariants.
3. Identify all affected callers/integrations.
4. Make the smallest coherent change in the owning layer.
5. Add a regression test that fails before the fix, plus integration/security coverage where boundaries are crossed.
6. Run applicable fast checks and full GitHub qualification.
7. Update the owning docs, API/migration notes and changelog.
8. Review the full diff for scope creep, secrets, test weakening, generated artifacts and regressions.
9. Open/update a PR; merge only when current-head gates and review pass.
10. Verify post-merge main CI/Security and the deployed/package outcome before marking the work complete.

Every handoff must include: source commit, changed paths, behavior delta, test commands/results, actual workflow URLs/conclusions, residual risks, migration/deploy instructions and the next acceptance gate.

This guide is the working completion contract. Evolve it when architecture or decisions change, but never turn planned functionality into a claim that it already exists.
