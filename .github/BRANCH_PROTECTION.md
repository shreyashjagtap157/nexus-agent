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

`main` is the canonical integration branch and currently contains the complete merged platform head. The GitHub repository default branch is still observed as `master`; `master` is kept fast-forwarded to the same commit as `main` only to prevent stale default-branch contents. The default-branch setting remains an administrator action and is intentionally enforced by the CI governance gate.

The main branch has been created as the canonical integration target and the multi-agent platform work is being integrated through a dedicated pull request.

Branch protection itself is a GitHub administration setting and must be enabled by a repository administrator with administration-level GitHub credentials. The source-controlled policy in this file is the authoritative expected configuration; it is not a substitute for the GitHub-side rule.
The policy is evaluated against the current main integration head by GitHub pull-request checks; stale cancelled runs are not merge evidence.
