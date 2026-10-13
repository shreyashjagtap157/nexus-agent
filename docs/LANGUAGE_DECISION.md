# Language and Runtime Decision for NexusAgent

> Independent assessment, deliberately ignoring the repository's current implementation.
> Date: 2026-10-13. Status: Recommended baseline; revisit only with evidence.

## Decision

**Python is the most suitable primary language for the central agent and research runtime.** Use TypeScript for the web frontend where appropriate. Use Rust for native clients or a narrowly scoped security-sensitive execution component only where its systems guarantees justify the extra complexity. Do not rewrite the entire platform into one language for ideological consistency.

## Requirements used

The product requires multi-agent planning and coordination; broad model/provider integrations; research, retrieval, document parsing and evidence qualification; local inference integrations; RAG and evaluation; MCP and browser automation; terminal/filesystem tools; asynchronous network I/O; durable sessions, memory and workflows; and rapid support for new AI capabilities.

Much of the central workload is I/O-bound while waiting for model, tool and network calls. Ecosystem breadth, integration velocity, observability and maintainability generally matter more than raw language benchmarks.

## Comparison

| Criterion | Python | TypeScript | Go | Rust |
|---|---|---|---|---|
| AI, research, RAG, parsing and evaluation ecosystem | Excellent | Good, narrower data/ML breadth | Narrower | Narrower high-level ecosystem |
| Provider and model integrations | Broad | Strong for web/provider APIs | Good for service APIs | Depends on available crates |
| I/O concurrency | Strong async ecosystem | Strong Node.js ecosystem | Excellent goroutines | Strong, more implementation complexity |
| Static safety | Requires disciplined typing plus runtime validation | Strong static types plus runtime schemas | Strong static types | Strong types, ownership and memory safety |
| Native/security-sensitive runtime | Limited low-level control | Limited low-level control | Good | Excellent |
| Rapid iteration across changing AI capabilities | Excellent | Very good | Good | More costly |
| Best fit here | Core orchestration, research and integrations | Browser UI | Optional future gateway/workers | Native and justified systems boundaries |

## Why Python wins as the core

1. Research and document-processing capabilities are central, not optional.
2. AI, retrieval, evaluation, local inference and provider ecosystems are broad and change quickly.
3. Many orchestration operations wait on external I/O, so compiled execution speed alone is unlikely to dominate end-to-end latency.
4. Python enables fast integration and experimentation without forcing every new capability behind another service boundary.
5. A rewrite would not solve provider failures, model latency, permission errors or workflow correctness.

This choice requires production discipline: type-checked interfaces, runtime schemas for model/tool/MCP data, explicit concurrency limits, timeouts, cancellation, retries, idempotency, structured errors, observability and process isolation for blocking or CPU-heavy tasks.

## Why not one language for everything?

- **TypeScript** is excellent for web UI and web-centric product backends, but is not the broadest fit for research, data processing and AI tooling.
- **Go** is excellent for concurrent services and compact deployments. Consider it for a measured gateway/worker bottleneck, not as a default rewrite.
- **Rust** offers strong memory/thread safety and performance for native clients, sandboxes and security-sensitive boundaries, but increases implementation cost across the broad AI integration surface.
- A polyglot architecture is allowed, not required: keep one authoritative orchestration runtime and split components only for a demonstrated security, deployment, reliability or scaling need.

## Recommended boundaries

- Python: agent loop, planner/orchestrator, workflow state, provider adapters, research/evidence pipeline, memory integration, MCP coordination, API/server and tool-policy orchestration.
- TypeScript: browser frontend and client-side state; a thin backend-for-frontend only if it solves a real need. Do not duplicate orchestration or authorization policy.
- Rust: native clients and narrowly scoped process/sandbox/security components when threat-model evidence justifies it.

## Reconsideration triggers

Re-evaluate only if representative profiling shows orchestration itself is a material bottleneck; deployment imposes strict memory/cold-start or single-binary constraints; a security boundary requires low-level memory-safe control; or a mandatory AI dependency materially changes the ecosystem trade-off. Compare representative workloads, integration completeness, security and operating cost—not synthetic language benchmarks alone.

## References

- Python asyncio: https://docs.python.org/3.13/library/asyncio.html
- Rust language project: https://www.rust-lang.org/

These sources describe language capabilities; the recommendation above is a project-specific engineering judgment, not a claim that one language is universally superior.
