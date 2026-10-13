# Main branch governance

main is the canonical integration branch for NexusAgent.

## Required repository settings

The GitHub repository administrator should configure these controls for main:

1. Require a pull request before merging.
2. Require at least one approving review.
3. Require review from Code Owners.
4. Dismiss stale approvals when new commits are pushed.
5. Require all required status checks before merging.
6. Require branches to be up to date before merging.
7. Require conversation resolution before merging.
8. Restrict force-pushes and branch deletion.
9. Apply the rules to administrators.
10. Allow only the repository's approved merge strategy, preferably squash merge for development PRs.
11. Require signed commits when the repository policy and contributor workflow support it.
12. Require the security and CI workflows in this repository before merge.

## Required checks

The protected branch should require the successful completion of the repository's CI/security gates, including:

- CI / Required
- Security / Required

The `CI / Required` job is the single authoritative application-quality gate and aggregates the complete Python, native, lint, version and audit validation matrix. Security remains a separate required control.

## Release policy

Release tags must be created from commits that are already reachable from main. The release workflow independently verifies that the tagged commit belongs to main history.

Published tags are immutable. Never force-push or rewrite a release tag.

## Current migration state

`main` is the canonical integration branch. The GitHub repository default branch is still observed as `master`; keep `master` fast-forwarded to `main` until an administrator changes the repository default. The default-branch setting remains an administrator action tracked in issue #326. CI reports a warning for this setting rather than allowing an unchangeable repository setting to masquerade as an application test failure.

The main branch has been created as the canonical integration target and the multi-agent platform work is being integrated through a dedicated pull request.

Branch protection itself is a GitHub administration setting and must be enabled by a repository administrator with administration-level GitHub credentials. The source-controlled policy in this file is the authoritative expected configuration; it is not a substitute for the GitHub-side rule.
The policy is evaluated against the current main integration head by GitHub pull-request checks; stale cancelled runs are not merge evidence.


## Verified repository settings snapshot (2026-10-13)

A live GitHub API read on 2026-10-13 reported the repository default branch as master, the main branch head as f338d8246dfa1d39a9a77cbc33e0996b8ef26432, main protection as disabled, and no repository rulesets. Therefore the policy above is a desired configuration, not an active enforcement guarantee. The default-branch and protection gaps remain unresolved until an administrator changes the GitHub-side settings and a fresh API read confirms the result. Re-check this snapshot before relying on it; it is intentionally dated and must not be treated as permanent state.
