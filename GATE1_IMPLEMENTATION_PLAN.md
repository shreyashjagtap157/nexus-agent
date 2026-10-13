# Gate 1 — Repository & Governance Baseline Implementation

## Current State
- **Local branch**: `master` (checked out)
- **Remote tracking**: `origin/master`, `origin/main`
- **Most recent merge**: PR #375 merged from `main` branch
- **Version**: `0.3.0-alpha.5` — synchronized across all manifests
- **Default branch** (GitHub): `master` (needs migration to `main`)
- **CI workflow**: Triggers on `push` and `pull_request` for branches `[main, master]`
- **Security workflow**: Triggers on `push` and `pull_request` for branches `[main, master]`
- **Governance job**: Reports warning if `default_branch != main`, exits 0 either way

## Required Actions (GitHub Admin)

### 1. Change Default Branch
- Navigate to GitHub repo Settings → Branches
- Change "Default branch" from `master` to `main`
- **Impact**: All `push`/`pull_request` workflows will now target `main` as the base branch
- **Note**: Issue #326 tracks this administrator-only setting change

### 2. Apply Branch Protection Rules
Enable the following protections on the `main` branch (Repository → Branches → `main` → Protect):

1. ✅ Require a pull request before merging
2. ✅ Require at least one approving review
3. ✅ Require review from Code Owners (add `CODEOWNERS` if not present)
4. ✅ Dismiss stale approvals when new commits are pushed
5. ✅ Require all required status checks before merging
6. ✅ Require branches to be up to date before merging
7. ✅ Require conversation resolution before merging
8. ✅ Restrict force-pushes and branch deletion
9. ✅ Apply rules to administrators
10. ✅ Allow only squash merge strategy (preferred for development PRs)
11. ✅ Require signed commits (if policy and contributor workflow support it)
12. ✅ Require CI / Required and Security / Required workflows before merge

### 3. Update CI Workflow Triggers
Modify `.github/workflows/ci.yml` and `.github/workflows/security.yml` to trigger only on `main`:

**ci.yml** — change:
```yaml
on:
  push:
    branches: ["main", "master"]    # →  branches: ["main"]
  pull_request:
    branches: ["main", "master"]    # →  branches: ["main"]
  workflow_dispatch:
```

**security.yml** — change similarly:
```yaml
on:
  push:
    branches: ["main", "master"]    # →  branches: ["main"]
  pull_request:
    branches: ["main", "master"]    # →  branches: ["main"]
  schedule:
    - cron: "23 2 * * 1"
  workflow_dispatch:
```

### 4. Verify Repository Settings
- Confirm `main` is the canonical integration branch (per ROADMAP.md #9)
- Ensure `.github/BRANCH_PROTECTION.md` policy is evaluated against `main` head
- Verify no PRs split between `master` and `main`
- Confirm repository protection settings are active (not just documented)

## Verification Checklist

### ✅ Codebase Synchronization (Already Verified)
- [x] VERSION = `0.3.0-alpha.5`
- [x] pyproject.toml version = `0.3.0-alpha.5`
- [x] src/nexus_agent/__init__.py __version__ = `0.3.0-alpha.5`
- [x] config/default.yaml version = `0.3.0-alpha.5`
- [x] src/nexus_agent/_default_config.yaml version = `0.3.0-alpha.5`
- [x] Version check script (scripts/check_version.py) passes

### ✅ Audit Coverage (Completed)
- [x] AGENTS.md — project overview, architecture, effort levels
- [x] README.md — product model, agent profiles, language decision
- [x] ARCHITECTURE.md — high-level architecture, logical boundaries 1-10
- [x] CODEBASE_AUDIT.md — module boundary map, must-fix items, maintainability
- [x] HYBRID_ARCHITECTURE.md — Rust/Python boundary, IPC protocol JSON-RPC 2.0
- [x] implementation_plan.md — Phase 1a complete, Phase 1b Ratatui TUI
- [x] ROADMAP.md — sequential qualification gates 1-5, alpha.5 hardening

### 📋 Pending Gates (After Branch Migration)

**Gate 2 — Multi-user Identity & Isolation** (ROADMAP.md #40-57):
- Define authentication, tenant/workspace membership, roles, session ownership
- Enforce authorization on APIs, background jobs, memory, provider secrets, artifacts
- Create local-mode bootstrap identity

**Phase 1b — Ratatui TUI Integration** (implementation_plan.md #43):
- Integrate Rust TUI app via ACP
- Implement layout engine with presets
- Build chat pane with streaming content display
- Add input bar with history, search, external editor
- Add status bar, task inspector, resource monitor
- Implement event handling (scroll, focus cycling, command palette)

**Rust CLI Enhancement**:
- Complete TUI integration in nexus-rs
- Window resize handling, graceful fallback to text mode

**Documentation Sync** (ROADMAP.md #128-138):
- Verify all 7 doc artifacts synchronized
- Add snapshot dates to historical audits
- Ensure language decision recommendations reflected

## Migration Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PRs splitting between master/main | Medium | High | Migrate default branch first, then close/master merge master→main |
| CI workflows missing commits | Low | Medium | Update workflow triggers before migrating default branch |
| Branch protection misconfiguration | Low | High | Apply all 12 controls from BRANCH_PROTECTION.md |
| Version drift during transition | Low | Medium | Run check_version.py before and after migration |
| Existing PRs targeting master | Medium | High | Ensure all open PRs target main after migration |

## Next Steps After Gate 1 Completion

1. **Gate 2**: Begin multi-user identity and isolation implementation
2. **Phase 1b**: Start Ratatui TUI integration (Rust side)
3. **Documentation**: Sync all 7 doc artifacts per ROADMAP.md #128-138
4. **Rust CLI**: Complete TUI integration in nexus-rs