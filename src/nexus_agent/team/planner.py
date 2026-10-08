"""Dynamic professional-team planner."""
from __future__ import annotations

import json
import uuid

from nexus_agent.llm.base import LLMProvider, Message, Role

from .models import AgentProfile, TeamConfig, TeamMode


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
        AgentProfile("architect", "Architect", "Software Architect", "Design the solution and integration boundaries.", "Inspect the repository and produce a concrete implementation strategy.", ["read", "search"], False),
        AgentProfile("implementer", "Implementer", "Implementation Engineer", "Implement the agreed changes.", "Modify only the required files and verify the changes.", ["read", "write", "shell", "git"], True),
        AgentProfile("tester", "Tester", "Test Engineer", "Validate behavior and regressions.", "Run focused and broad tests and report reproducible failures.", ["read", "search", "shell"], False, True),
        AgentProfile("reviewer", "Reviewer", "Code Reviewer", "Independently review the changes.", "Look for defects, compatibility problems and incomplete integration.", ["read", "search"], False, True),
    ],
    TeamMode.RESEARCH: [
        AgentProfile("researcher", "Primary Researcher", "Primary-Source Researcher", "Gather authoritative evidence.", "Prefer specifications, standards, papers and primary documentation.", ["read", "web"], False),
        AgentProfile("analyst", "Analyst", "Domain Analyst", "Analyze the collected evidence.", "Compare sources and derive explicit conclusions with provenance.", ["read", "web"], False),
        AgentProfile("skeptic", "Skeptic", "Contradiction Analyst", "Challenge findings and seek counterevidence.", "Actively search for contradictory evidence and hidden assumptions.", ["read", "web"], False, True),
        AgentProfile("verifier", "Verifier", "Evidence Verifier", "Independently verify important claims.", "Check claims against source evidence and reject unsupported assertions.", ["read", "web"], False, True),
    ],
    TeamMode.REVIEW: [
        AgentProfile("reviewer-a", "Reviewer A", "Independent Reviewer", "Review the target from a correctness perspective.", "Inspect requirements, behavior and implementation quality.", ["read", "search"], False, True),
        AgentProfile("reviewer-b", "Reviewer B", "Adversarial Reviewer", "Search for failures and counterexamples.", "Look for edge cases, regressions and unsupported assumptions.", ["read", "search", "shell"], False, True),
        AgentProfile("integrator", "Integrator", "Review Integrator", "Synthesize review findings.", "Turn independent findings into an actionable prioritized result.", ["read", "search"], False, True),
    ],
    TeamMode.ANALYSIS: [
        AgentProfile("lead", "Lead Analyst", "Systems Analyst", "Decompose and analyze the problem.", "Map dependencies, constraints and unknowns.", ["read", "search"], False),
        AgentProfile("specialist", "Domain Specialist", "Subject-Matter Specialist", "Investigate the hardest domain-specific questions.", "Produce concrete technical findings.", ["read", "search"], False),
        AgentProfile("skeptic", "Skeptic", "Critical Analyst", "Challenge assumptions and alternatives.", "Search for contradictions and missing cases.", ["read", "search"], False, True),
    ],
    TeamMode.PLAN: [
        AgentProfile("planner", "Planner", "Systems Planner", "Construct an executable plan.", "Produce concrete work packages and dependencies.", ["read", "search"], False),
        AgentProfile("risk", "Risk Reviewer", "Risk Analyst", "Challenge the proposed sequencing and assumptions.", "Identify failure modes and safer alternatives.", ["read", "search"], False, True),
    ],
    TeamMode.AUTOMATION: [
        AgentProfile("designer", "Automation Designer", "Workflow Architect", "Design a reliable automation flow.", "Define triggers, state, retries, permissions and outputs.", ["read", "search"], False),
        AgentProfile("operator", "Automation Operator", "Automation Engineer", "Implement the automation.", "Make the smallest safe set of changes and validate execution.", ["read", "write", "shell"], True),
        AgentProfile("tester", "Automation Tester", "Reliability Engineer", "Exercise failure and recovery paths.", "Test retries, idempotency and partial failures.", ["read", "shell"], False, True),
    ],
}


def infer_mode(goal: str, mode: TeamMode) -> TeamMode:
    if mode != TeamMode.AUTO:
        return mode
    text = goal.lower()
    if any(x in text for x in ("research", "sources", "paper", "evidence", "literature", "specification")):
        return TeamMode.RESEARCH
    if any(x in text for x in ("fix", "implement", "code", "bug", "refactor", "compile", "test", "repository")):
        return TeamMode.CODE
    if any(x in text for x in ("review", "audit", "verify", "inspect")):
        return TeamMode.REVIEW
    if any(x in text for x in ("automate", "automation", "workflow", "schedule", "pipeline")):
        return TeamMode.AUTOMATION
    if any(x in text for x in ("plan", "roadmap", "architecture design")):
        return TeamMode.PLAN
    return TeamMode.ANALYSIS


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
        required = [str(item.get(k, "")).strip() for k in ("name", "profession", "mission", "instructions")]
        if not all(required):
            continue
        base = "-".join(required[0].lower().split())[:32] or uuid.uuid4().hex[:8]
        role_id = base
        n = 2
        while role_id in seen:
            role_id = f"{base}-{n}"
            n += 1
        seen.add(role_id)
        profiles.append(
            AgentProfile(
                role_id=role_id,
                name=required[0],
                profession=required[1],
                mission=required[2],
                instructions=required[3],
                tool_categories=[str(x) for x in item.get("tool_categories", []) if x],
                write_access=bool(item.get("write_access", False)),
                reviewer=bool(item.get("reviewer", False)),
                dependencies=[str(x) for x in item.get("dependencies", []) if x],
                model_role=str(item.get("model_role", "default")),
            )
        )
        if len(profiles) >= max_agents:
            break

    fallback = FALLBACKS.get(mode, FALLBACKS[TeamMode.ANALYSIS])
    if len(profiles) < max_agents:
        for profile in fallback:
            if profile.role_id not in seen:
                profiles.append(profile)
                seen.add(profile.role_id)
            if len(profiles) >= max_agents:
                break

    return profiles[:max_agents]


def generate_team(provider: LLMProvider, goal: str, config: TeamConfig) -> tuple[TeamMode, list[AgentProfile]]:
    mode = infer_mode(goal, config.mode)
    prompt = f"""Task:
{goal}

Mode:
{mode.value}

Maximum team size:
{config.max_agents}

Return JSON:
{{"agents":[{{"name":"...","profession":"...","mission":"...","instructions":"...","tool_categories":["read","write","shell","web","git"],"write_access":false,"reviewer":false,"dependencies":[],"model_role":"default"}}]}}
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

    if not profiles:
        profiles = list(FALLBACKS.get(mode, FALLBACKS[TeamMode.ANALYSIS]))[: config.max_agents]

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
        profiles[-1].instructions += "\nIndependently review the work of the other team members before completing."

    return mode, profiles
