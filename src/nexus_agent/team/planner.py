"""Dynamic professional-team planner."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import replace

from nexus_agent.llm.base import LLMProvider, Message, Role

from .models import AgentProfile, TeamConfig, TeamMode
from .research import policy as research_policy


SYSTEM_PROMPT = """You are NexusAgent's team architect.

Build a professional multi-agent team for the user's task. Do not solve the task.
Each worker must have a distinct responsibility and should be able to operate independently
while communicating through a shared team blackboard.

Prefer:
- independent specialists for the hardest parts;
- one or more implementation workers only when the task requires changes;
- at least one reviewer/adversarial role for non-trivial work;
- restricted tool access according to the role;
- explicit evidence, artifacts, commands or tests as expected outputs.

Return JSON only.
"""

FALLBACKS: dict[TeamMode, list[AgentProfile]] = {
    TeamMode.CODE: [
        AgentProfile(
            "architect",
            "Architect",
            "Software Architect",
            "Design the solution and integration boundaries.",
            "Inspect the repository and produce a concrete implementation strategy.",
            ["read", "search"],
            False,
        ),
        AgentProfile(
            "implementer",
            "Implementer",
            "Implementation Engineer",
            "Implement the agreed changes.",
            "Modify only the required files and verify the changes.",
            ["read", "write", "shell", "git"],
            True,
        ),
        AgentProfile(
            "tester",
            "Tester",
            "Test Engineer",
            "Validate behavior and regressions.",
            "Run focused and broad tests and report reproducible failures.",
            ["read", "search", "shell"],
            False,
            True,
        ),
        AgentProfile(
            "reviewer",
            "Reviewer",
            "Code Reviewer",
            "Independently review the changes.",
            "Look for defects, compatibility problems and incomplete integration.",
            ["read", "search"],
            False,
            True,
        ),
    ],
    TeamMode.RESEARCH: [
        AgentProfile(
            "researcher",
            "Primary Researcher",
            "Primary-Source Research Scientist",
            "Gather authoritative evidence.",
            "Prefer specifications, standards, papers and first-party documentation; preserve exact provenance.",
            ["read", "web", "research"],
            False,
        ),
        AgentProfile(
            "researcher-secondary",
            "Independent Researcher",
            "Independent Research Scientist",
            "Gather independent corroborating evidence.",
            "Use different search paths and source families from the primary researcher.",
            ["read", "web", "research"],
            False,
        ),
        AgentProfile(
            "analyst",
            "Domain Analyst",
            "Domain Analysis Specialist",
            "Analyze collected evidence.",
            "Compare sources and derive explicit conclusions with provenance.",
            ["read", "web", "research"],
            False,
            False,
            ["researcher"],
        ),
        AgentProfile(
            "evidence-verifier",
            "Evidence Verifier",
            "Evidence Verification Specialist",
            "Verify high-value claims.",
            "Check claims against exact source evidence and reject unsupported assertions.",
            ["read", "web", "research"],
            False,
            True,
            ["analyst"],
        ),
        AgentProfile(
            "skeptic",
            "Contradiction Skeptic",
            "Adversarial Contradiction Analyst",
            "Find disagreement and counterevidence.",
            "Actively seek contradictory source evidence and hidden assumptions.",
            ["read", "web", "research"],
            False,
            True,
            ["analyst"],
        ),
        AgentProfile(
            "formal",
            "Formal Methods Specialist",
            "Formal Verification Specialist",
            "Assess formal consistency and proof obligations.",
            "Translate relevant claims into machine-checkable obligations where possible.",
            ["read", "search", "shell", "formal"],
            False,
            True,
            ["analyst"],
        ),
        AgentProfile(
            "implementability",
            "Implementability Engineer",
            "Compiler and Systems Implementability Specialist",
            "Determine whether proposed mechanisms can be built.",
            "Map semantics and requirements to real compiler, runtime, OS and hardware implementation techniques.",
            ["read", "search", "shell", "code_intel", "formal"],
            False,
            True,
            ["analyst"],
        ),
        AgentProfile(
            "standards",
            "Standards Analyst",
            "Standards and Specification Specialist",
            "Compare requirements against standards.",
            "Prefer normative standards and distinguish mandatory requirements from recommendations.",
            ["read", "web", "research"],
            False,
            False,
            ["researcher"],
        ),
        AgentProfile(
            "academic",
            "Academic Literature Analyst",
            "Programming-Language Research Specialist",
            "Analyze peer-reviewed and preprint literature.",
            "Trace claims to research papers and identify open research questions.",
            ["read", "web", "research"],
            False,
            False,
            ["researcher"],
        ),
        AgentProfile(
            "bibliography",
            "Bibliography Curator",
            "Evidence and Provenance Curator",
            "Maintain source provenance.",
            "Deduplicate sources, classify source quality and preserve citation-ready metadata.",
            ["read", "web", "research"],
            False,
            False,
            ["researcher"],
        ),
        AgentProfile(
            "ecosystem",
            "Ecosystem Analyst",
            "Technology Ecosystem Specialist",
            "Map ecosystem dependencies.",
            "Evaluate toolchains, package managers, runtimes and compatibility constraints.",
            ["read", "web", "research"],
            False,
            False,
            ["analyst"],
        ),
        AgentProfile(
            "interoperability",
            "Interoperability Architect",
            "Systems Interoperability Specialist",
            "Evaluate interfaces and compatibility.",
            "Assess FFI, ABI, OS, hardware and cross-language interoperability.",
            ["read", "search", "formal"],
            False,
            False,
            ["implementability"],
        ),
        AgentProfile(
            "complexity",
            "Complexity Analyst",
            "Resource and Complexity Specialist",
            "Analyze computational resources.",
            "Assess time, space, allocation, concurrency and asymptotic costs.",
            ["read", "search", "formal"],
            False,
            False,
            ["formal"],
        ),
        AgentProfile(
            "security",
            "Security Analyst",
            "Security and Threat Modeling Specialist",
            "Assess security implications.",
            "Identify trust boundaries, attack surfaces and unsafe assumptions.",
            ["read", "search", "web", "formal"],
            False,
            True,
            ["analyst"],
        ),
        AgentProfile(
            "concurrency",
            "Concurrency Specialist",
            "Concurrency and Distributed Systems Specialist",
            "Review concurrency semantics.",
            "Analyze scheduling, synchronization, cancellation, deadlocks and distributed execution.",
            ["read", "search", "formal"],
            False,
            False,
            ["formal"],
        ),
        AgentProfile(
            "type-theory",
            "Type Theory Specialist",
            "Type Systems and Logic Specialist",
            "Assess type-theoretic foundations.",
            "Analyze typing rules, inference, normalization and consistency obligations.",
            ["read", "search", "formal"],
            False,
            False,
            ["formal"],
        ),
        AgentProfile(
            "semantics",
            "Semantics Specialist",
            "Programming-Language Semantics Specialist",
            "Assess formal semantics.",
            "Map syntax to operational, denotational or executable semantics and identify ambiguity.",
            ["read", "search", "formal"],
            False,
            False,
            ["type-theory"],
        ),
        AgentProfile(
            "language-design",
            "Language Design Specialist",
            "Programming-Language Design Specialist",
            "Assess language coherence.",
            "Review syntax, ergonomics, compositionality, orthogonality and evolution constraints.",
            ["read", "search", "research"],
            False,
            False,
            ["analyst"],
        ),
        AgentProfile(
            "compiler",
            "Compiler Architect",
            "Compiler Implementation Specialist",
            "Assess compiler realization.",
            "Map language constructs to lexer, parser, IR, optimization, backend and code generation requirements.",
            ["read", "search", "shell", "code_intel", "formal"],
            False,
            True,
            ["implementability"],
        ),
        AgentProfile(
            "runtime",
            "Runtime Architect",
            "Runtime and VM Specialist",
            "Assess runtime realization.",
            "Map semantics to memory, scheduling, GC/ownership, exceptions, IO and runtime services.",
            ["read", "search", "formal"],
            False,
            False,
            ["implementability"],
        ),
        AgentProfile(
            "hardware",
            "Hardware Analyst",
            "Computer Architecture and Hardware Specialist",
            "Assess hardware feasibility.",
            "Evaluate CPU, GPU, NPU, memory hierarchy and accelerator constraints.",
            ["read", "web", "research"],
            False,
            False,
            ["implementability"],
        ),
        AgentProfile(
            "os",
            "OS Integration Specialist",
            "Operating Systems Integration Specialist",
            "Assess OS integration.",
            "Analyze process, threading, filesystem, networking, security and system-call requirements.",
            ["read", "web", "research"],
            False,
            False,
            ["interoperability"],
        ),
        AgentProfile(
            "reproducibility",
            "Reproducibility Curator",
            "Reproducibility and Artifact Specialist",
            "Preserve reproducibility.",
            "Track versions, hashes, environments and artifact lineage required to reproduce results.",
            ["read", "search", "git", "research"],
            False,
            False,
            ["bibliography"],
        ),
        AgentProfile(
            "historian",
            "Technology Historian",
            "Technology History Analyst",
            "Trace historical precedent.",
            "Determine what has been attempted, why it worked or failed and which constraints changed.",
            ["read", "web", "research"],
            False,
            False,
            ["researcher"],
        ),
        AgentProfile(
            "future-tech",
            "Future Technology Analyst",
            "Emerging Technology Specialist",
            "Assess plausible upcoming technologies.",
            "Separate roadmap statements from demonstrated capabilities and evaluate upgrade compatibility.",
            ["read", "web", "research"],
            False,
            False,
            ["ecosystem"],
        ),
        AgentProfile(
            "requirements",
            "Requirements Engineer",
            "Requirements and Systems Specification Specialist",
            "Normalize requirements.",
            "Turn vague requirements into explicit acceptance criteria, invariants and traceable obligations.",
            ["read", "search", "research"],
            False,
            False,
            ["analyst"],
        ),
        AgentProfile(
            "model-checker",
            "Model Checker",
            "Formal Model-Checking Specialist",
            "Search formal state spaces.",
            "Use machine-checkable models when available and report bounds and counterexamples.",
            ["read", "search", "shell", "formal"],
            False,
            True,
            ["formal"],
        ),
        AgentProfile(
            "proof-engineer",
            "Proof Engineer",
            "Interactive Theorem Proving Specialist",
            "Construct proof artifacts.",
            "Use theorem provers where available and distinguish machine-checked proofs from informal arguments.",
            ["read", "search", "shell", "formal"],
            False,
            True,
            ["formal"],
        ),
        AgentProfile(
            "data-quality",
            "Data Quality Analyst",
            "Research Data Quality Specialist",
            "Audit collected research data.",
            "Find missing metadata, duplicates, stale content and provenance defects.",
            ["read", "search", "research"],
            False,
            False,
            ["bibliography"],
        ),
        AgentProfile(
            "claim-auditor",
            "Claim Auditor",
            "Claim-Level Audit Specialist",
            "Audit claim/evidence mappings.",
            "Ensure each material claim has adequate evidence, provenance and verification status.",
            ["read", "search", "research"],
            False,
            True,
            ["evidence-verifier"],
        ),
        AgentProfile(
            "conflict-adjudicator",
            "Conflict Adjudicator",
            "Evidence Conflict Resolution Specialist",
            "Resolve source conflicts.",
            "Classify contradictions and document why one evidence set is preferred or why uncertainty remains.",
            ["read", "web", "research", "formal"],
            False,
            True,
            ["skeptic", "evidence-verifier"],
        ),
        AgentProfile(
            "synthesis",
            "Evidence Synthesizer",
            "Research Synthesis Specialist",
            "Integrate verified findings.",
            "Construct a coherent evidence map without silently resolving contradictions.",
            ["read", "search", "research"],
            False,
            False,
            ["claim-auditor", "conflict-adjudicator"],
        ),
        AgentProfile(
            "writer",
            "Technical Writer",
            "Evidence-Constrained Technical Writer",
            "Prepare the report structure.",
            "Use only approved evidence and preserve claim identifiers and citations.",
            ["read", "research"],
            False,
            False,
            ["synthesis"],
        ),
        AgentProfile(
            "final-auditor",
            "Final Evidence Auditor",
            "Final Research Quality Auditor",
            "Perform the final audit.",
            "Challenge unsupported language, missing citations and overclaimed certainty before release.",
            ["read", "research", "formal"],
            False,
            True,
            ["writer"],
        ),
        AgentProfile(
            "independent-auditor",
            "Independent Auditor",
            "Independent Reproducibility Auditor",
            "Repeat critical checks independently.",
            "Audit the evidence set from a separate reasoning path and report residual uncertainty.",
            ["read", "web", "research", "formal"],
            False,
            True,
            ["final-auditor"],
        ),
        AgentProfile(
            "source-metadata",
            "Source Metadata Specialist",
            "Source Metadata and Archival Specialist",
            "Preserve source identity.",
            "Record titles, dates, versions, URLs and stable identifiers for every material source.",
            ["read", "web", "research"],
            False,
            False,
            ["bibliography"],
        ),
        AgentProfile(
            "citation",
            "Citation Specialist",
            "Citation and Bibliographic Verification Specialist",
            "Validate citation integrity.",
            "Check that referenced source identifiers, quotations and URLs remain aligned.",
            ["read", "web", "research"],
            False,
            True,
            ["claim-auditor"],
        ),
        AgentProfile(
            "upgrade",
            "Upgrade Analyst",
            "Technology Upgrade Path Specialist",
            "Evaluate future upgrades.",
            "Assess migration paths, compatibility risks and technology replacement boundaries.",
            ["read", "web", "research"],
            False,
            False,
            ["future-tech"],
        ),
        AgentProfile(
            "scalability",
            "Scalability Analyst",
            "Systems Scalability and Performance Specialist",
            "Assess scalability limits.",
            "Analyze throughput, latency, resource scaling, benchmarking and bottlenecks across the proposed system.",
            ["read", "search", "formal"],
            False,
            False,
            ["complexity"],
        ),
        AgentProfile(
            "portability",
            "Portability Analyst",
            "Cross-Platform Portability Specialist",
            "Assess deployment portability.",
            "Analyze operating-system, architecture, toolchain and platform compatibility constraints.",
            ["read", "search", "research"],
            False,
            False,
            ["interoperability", "os"],
        ),
    ],
    TeamMode.REVIEW: [
        AgentProfile(
            "reviewer-a",
            "Reviewer A",
            "Independent Reviewer",
            "Review the target from a correctness perspective.",
            "Inspect requirements, behavior and implementation quality.",
            ["read", "search"],
            False,
            True,
        ),
        AgentProfile(
            "reviewer-b",
            "Reviewer B",
            "Adversarial Reviewer",
            "Search for failures and counterexamples.",
            "Look for edge cases, regressions and unsupported assumptions.",
            ["read", "search", "shell"],
            False,
            True,
        ),
        AgentProfile(
            "integrator",
            "Integrator",
            "Review Integrator",
            "Synthesize review findings.",
            "Turn independent findings into an actionable prioritized result.",
            ["read", "search"],
            False,
            True,
        ),
    ],
    TeamMode.ANALYSIS: [
        AgentProfile(
            "lead",
            "Lead Analyst",
            "Systems Analyst",
            "Decompose and analyze the problem.",
            "Map dependencies, constraints and unknowns.",
            ["read", "search"],
            False,
        ),
        AgentProfile(
            "specialist",
            "Domain Specialist",
            "Subject-Matter Specialist",
            "Investigate the hardest domain-specific questions.",
            "Produce concrete technical findings.",
            ["read", "search"],
            False,
        ),
        AgentProfile(
            "skeptic",
            "Skeptic",
            "Critical Analyst",
            "Challenge assumptions and alternatives.",
            "Search for contradictions and missing cases.",
            ["read", "search"],
            False,
            True,
        ),
    ],
    TeamMode.PLAN: [
        AgentProfile(
            "planner",
            "Planner",
            "Systems Planner",
            "Construct an executable plan.",
            "Produce concrete work packages and dependencies.",
            ["read", "search"],
            False,
        ),
        AgentProfile(
            "risk",
            "Risk Reviewer",
            "Risk Analyst",
            "Challenge the proposed sequencing and assumptions.",
            "Identify failure modes and safer alternatives.",
            ["read", "search"],
            False,
            True,
        ),
    ],
    TeamMode.AUTOMATION: [
        AgentProfile(
            "designer",
            "Automation Designer",
            "Workflow Architect",
            "Design a reliable automation flow.",
            "Define triggers, state, retries, permissions and outputs.",
            ["read", "search"],
            False,
        ),
        AgentProfile(
            "operator",
            "Automation Operator",
            "Automation Engineer",
            "Implement the automation.",
            "Make the smallest safe set of changes and validate execution.",
            ["read", "write", "shell"],
            True,
        ),
        AgentProfile(
            "tester",
            "Automation Tester",
            "Reliability Engineer",
            "Exercise failure and recovery paths.",
            "Test retries, idempotency and partial failures.",
            ["read", "shell"],
            False,
            True,
        ),
    ],
}


def infer_mode(goal: str, mode: TeamMode) -> TeamMode:
    if mode != TeamMode.AUTO:
        return mode
    text = goal.lower()
    if any(
        x in text
        for x in ("research", "sources", "paper", "evidence", "literature", "specification")
    ):
        return TeamMode.RESEARCH
    if any(
        x in text
        for x in ("fix", "implement", "code", "bug", "refactor", "compile", "test", "repository")
    ):
        return TeamMode.CODE
    if any(x in text for x in ("review", "audit", "verify", "inspect")):
        return TeamMode.REVIEW
    if any(x in text for x in ("automate", "automation", "workflow", "schedule", "pipeline")):
        return TeamMode.AUTOMATION
    if any(x in text for x in ("plan", "roadmap", "architecture design")):
        return TeamMode.PLAN
    return TeamMode.ANALYSIS


def _slug(value: str, fallback: str = "agent") -> str:
    text = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower())
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return (text or fallback)[:64]


def _parse_profiles(raw: str, mode: TeamMode, max_agents: int) -> list[AgentProfile]:
    try:
        payload = json.loads(raw)
        items = payload.get("agents", []) if isinstance(payload, dict) else []
    except json.JSONDecodeError:
        items = []

    profiles: list[AgentProfile] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        required = [
            str(item.get(k, "")).strip() for k in ("name", "profession", "mission", "instructions")
        ]
        if not all(required):
            continue

        base = _slug(
            str(item.get("id") or item.get("role_id") or required[0]),
            "agent",
        )
        role_id = base
        suffix = 2
        while role_id in seen:
            role_id = f"{base}-{suffix}"
            suffix += 1
        seen.add(role_id)

        profiles.append(
            AgentProfile(
                role_id=role_id,
                name=required[0],
                profession=required[1],
                mission=required[2],
                instructions=required[3],
                tool_categories=[
                    str(x).strip() for x in item.get("tool_categories", []) if str(x).strip()
                ],
                write_access=bool(item.get("write_access", False)),
                reviewer=bool(item.get("reviewer", False)),
                dependencies=[
                    _slug(str(x)) for x in item.get("dependencies", []) if str(x).strip()
                ],
                model_role=_slug(str(item.get("model_role", "default")), "default"),
                provider=str(item.get("provider")) if item.get("provider") else None,
                model=str(item.get("model")) if item.get("model") else None,
                fallbacks=[str(x).strip() for x in item.get("fallbacks", []) if str(x).strip()],
                skill_ids=[_slug(str(x)) for x in item.get("skill_ids", []) if str(x).strip()],
            )
        )
        if len(profiles) >= max_agents:
            break

    fallback = FALLBACKS.get(mode, FALLBACKS[TeamMode.ANALYSIS])
    if len(profiles) < max_agents:
        for profile in fallback:
            if profile.role_id not in seen:
                clone = replace(
                    profile,
                    tool_categories=list(profile.tool_categories),
                    dependencies=list(profile.dependencies),
                    fallbacks=list(profile.fallbacks),
                    skill_ids=list(profile.skill_ids),
                )
                profiles.append(clone)
                seen.add(clone.role_id)
            if len(profiles) >= max_agents:
                break

    # Normalize dependency references against generated IDs, names and professions.
    aliases: dict[str, str] = {}
    for profile in profiles:
        aliases[_slug(profile.role_id)] = profile.role_id
        aliases[_slug(profile.name)] = profile.role_id
        aliases[_slug(profile.profession)] = profile.role_id

    for profile in profiles:
        normalized: list[str] = []
        for dependency in profile.dependencies:
            resolved = aliases.get(_slug(dependency))
            if resolved and resolved != profile.role_id and resolved not in normalized:
                normalized.append(resolved)
            elif not resolved:
                # Preserve unresolved dependencies so the scheduler can fail closed
                # instead of silently turning a dependent worker into an independent one.
                unresolved = _slug(dependency)
                if unresolved and unresolved != profile.role_id and unresolved not in normalized:
                    normalized.append(unresolved)
        profile.dependencies = normalized

    return profiles[:max_agents]


def generate_team(
    provider: LLMProvider,
    goal: str,
    config: TeamConfig,
    saved_agents: list[AgentProfile] | None = None,
) -> tuple[TeamMode, list[AgentProfile]]:
    mode = infer_mode(goal, config.mode)
    if mode == TeamMode.RESEARCH:
        from .research import policy as research_policy

        depth_floor = int(research_policy(config.research_depth)["role_floor"])
        config.max_agents = max(config.max_agents, min(depth_floor, 64))
        config.parallelism = min(config.parallelism, config.max_agents)
    depth_data = (
        research_policy(config.research_depth)
        if mode == TeamMode.RESEARCH
        else {
            "name": "not_applicable",
            "label": "Not applicable",
            "role_floor": config.max_agents,
            "query_rounds": 0,
            "sources_per_query": 0,
            "verification_passes": 0,
        }
    )
    saved = saved_agents or []
    prompt = f"""Task:
{goal}

Mode:
{mode.value}

Maximum team size:
{config.max_agents}

Research depth:
{config.research_depth if mode == TeamMode.RESEARCH else "not_applicable"}

Research collection policy:
{config.research_collection}

Research policy:
{json.dumps(depth_data, ensure_ascii=False)}

Saved agent profiles available for reuse:
{json.dumps([p.__dict__ for p in saved], ensure_ascii=False)}

Create a distinct professional team. This is the one-time deployment/planning phase.
After deployment, workers execute their missions and review evidence; they must not recursively
re-plan or regenerate the team unless the user explicitly requests a new plan.
Prefer specialist workers over coordinator duplicates. Reuse relevant saved profiles instead of
recreating them. Do not remove or weaken pinned roles; the runtime will preserve pinned roles.
Return JSON only:
{{"agents":[{{"id":"stable-role-id","name":"...","profession":"...","mission":"...","instructions":"...","tool_categories":["read","write","shell","web","git","mcp","browser","code_intel","lsp","memory","research"],"write_access":false,"reviewer":false,"dependencies":[],"model_role":"default","skill_ids":[]}}]}}
"""
    try:
        response = provider.chat_completion(
            [
                Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
                Message(role=Role.USER, content=prompt),
            ],
            temperature=0.0,
            max_tokens=5000,
        )
        profiles = _parse_profiles(response.content or "", mode, config.max_agents)
    except (RuntimeError, ValueError, OSError, TypeError):
        profiles = _parse_profiles("{}", mode, config.max_agents)

    if saved:
        existing = {p.role_id for p in profiles}
        for saved_profile in saved:
            if saved_profile.role_id not in existing:
                profiles.append(saved_profile)
                existing.add(saved_profile.role_id)
            if len(profiles) >= config.max_agents:
                break

    if not profiles:
        profiles = [
            replace(
                profile,
                tool_categories=list(profile.tool_categories),
                dependencies=list(profile.dependencies),
                fallbacks=list(profile.fallbacks),
                skill_ids=list(profile.skill_ids),
            )
            for profile in list(FALLBACKS.get(mode, FALLBACKS[TeamMode.ANALYSIS]))[
                : config.max_agents
            ]
        ]

    if not config.allow_parallel_writers:
        seen_writer = False
        for profile in profiles:
            if profile.write_access:
                if seen_writer:
                    profile.write_access = False
                    profile.tool_categories = [x for x in profile.tool_categories if x != "write"]
                else:
                    seen_writer = True

    if config.require_reviewer and profiles and not any(p.reviewer for p in profiles):
        profiles[-1].reviewer = True
        profiles[
            -1
        ].instructions += (
            "\nIndependently review the work of the other team members before completing."
        )

    return mode, profiles
