"""
Reflection & Critic Loops — Generator-Critic validation pattern.

After the agent produces a solution, a secondary "Critic" pass evaluates
it before presenting to the user. Implements self-correction chains that
improve output quality through iterative refinement.

Features:
- Structured critique with scoring (0-100)
- Issue identification and suggestion generation
- Self-correction chain (critique → fix → re-evaluate)
- Configurable quality threshold and max reflection rounds
- Integration-ready for agent loop post-processing
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CritiqueIssue:
    """A single issue identified during critique."""
    category: str          # correctness, completeness, quality, security, performance
    severity: str          # critical, major, minor, suggestion
    description: str
    location: str = ""     # file:line or general area
    fix_suggestion: str = ""


@dataclass
class CritiqueResult:
    """Result of a critic evaluation pass."""
    score: int                                     # 0-100 quality score
    approved: bool                                 # True if score >= threshold
    issues: list[CritiqueIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""
    reasoning: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "major")

    def to_feedback_prompt(self) -> str:
        """Convert critique result to a feedback prompt for the generator."""
        lines = [
            "## 🔍 Self-Reflection Critique Results",
            "",
            f"**Quality Score:** {self.score}/100 {'✅' if self.approved else '❌'}",
            f"**Issues Found:** {len(self.issues)} "
            f"({self.critical_count} critical, {self.major_count} major)",
            "",
        ]

        if self.summary:
            lines.extend(["### Summary", self.summary, ""])

        if self.issues:
            lines.append("### Issues to Fix")
            for i, issue in enumerate(self.issues, 1):
                severity_icon = {
                    "critical": "🔴",
                    "major": "🟠",
                    "minor": "🟡",
                    "suggestion": "💡",
                }.get(issue.severity, "•")
                lines.append(
                    f"{i}. {severity_icon} **[{issue.category}]** {issue.description}"
                )
                if issue.fix_suggestion:
                    lines.append(f"   → Fix: {issue.fix_suggestion}")

        if self.suggestions:
            lines.extend(["", "### Improvement Suggestions"])
            for s in self.suggestions:
                lines.append(f"- {s}")

        lines.extend([
            "",
            "**Please address the issues above and regenerate your response.**",
        ])

        return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Critic prompt templates                                                      #
# --------------------------------------------------------------------------- #

CRITIC_SYSTEM_PROMPT = """You are a rigorous code and response critic. Your job is to evaluate 
the quality of an AI assistant's output and identify issues.

You MUST respond with a valid JSON object containing exactly these fields:
{
    "score": <integer 0-100>,
    "summary": "<1-2 sentence summary of quality>",
    "reasoning": "<brief explanation of your scoring rationale>",
    "issues": [
        {
            "category": "<correctness|completeness|quality|security|performance>",
            "severity": "<critical|major|minor|suggestion>",
            "description": "<what is wrong>",
            "location": "<where in the output>",
            "fix_suggestion": "<how to fix it>"
        }
    ],
    "suggestions": ["<improvement suggestion>"]
}

Scoring Guide:
- 90-100: Excellent — production ready, no significant issues
- 70-89: Good — minor improvements needed
- 50-69: Adequate — several issues that should be addressed
- 30-49: Poor — significant problems requiring rework
- 0-29: Unacceptable — fundamental issues

Be strict but fair. Focus on:
1. Correctness — Is the code/answer factually correct?
2. Completeness — Does it fully address the user's request?
3. Quality — Is the code well-structured, readable, and idiomatic?
4. Security — Are there any security concerns?
5. Performance — Are there obvious performance issues?
"""


def _build_critic_prompt(user_request: str, agent_output: str) -> str:
    """Build the evaluation prompt for the critic."""
    return (
        f"## User Request\n{user_request}\n\n"
        f"## Assistant Output to Evaluate\n{agent_output}\n\n"
        "Please evaluate the above output and respond with the JSON critique."
    )


def _parse_critique_response(response_text: str) -> CritiqueResult:
    """Parse the LLM critique response into a CritiqueResult.

    Handles both clean JSON and JSON embedded in markdown code blocks.
    """
    text = response_text.strip()

    # Strip code fences first
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines if they are code fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try to extract JSON from markdown code blocks
    if "```" in text:
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("Failed to parse critic response as JSON")
                return CritiqueResult(
                    score=50,
                    approved=False,
                    summary="Could not parse critique response",
                    reasoning=text[:500],
                )
        else:
            return CritiqueResult(
                score=50,
                approved=False,
                summary="Could not parse critique response",
                reasoning=text[:500],
            )

    # Parse issues
    issues: list[CritiqueIssue] = []
    for issue_data in data.get("issues", []):
        issues.append(CritiqueIssue(
            category=issue_data.get("category", "quality"),
            severity=issue_data.get("severity", "minor"),
            description=issue_data.get("description", ""),
            location=issue_data.get("location", ""),
            fix_suggestion=issue_data.get("fix_suggestion", ""),
        ))

    score = max(0, min(100, int(data.get("score") or 50)))

    return CritiqueResult(
        score=score,
        approved=False,  # Will be overridden by threshold in evaluate()
        issues=issues,
        suggestions=data.get("suggestions", []),
        summary=data.get("summary", ""),
        reasoning=data.get("reasoning", ""),
    )


class ReflectionEngine:
    """Generator-Critic self-evaluation engine.

    After the agent generates a response, the reflection engine
    evaluates it using a critic prompt and optionally triggers
    self-correction if the quality score is below threshold.

    Usage:
        engine = ReflectionEngine(provider=llm, threshold=70)
        critique = engine.evaluate(
            user_request="Fix the bug in utils.py",
            agent_output="I modified line 42...",
        )
        if not critique.approved:
            feedback = critique.to_feedback_prompt()
            # Feed feedback back to the generator
    """

    def __init__(
        self,
        provider: Any = None,
        threshold: int = 70,
        max_rounds: int = 2,
        temperature: float = 0.2,
    ):
        """Initialize the reflection engine.

        Args:
            provider: LLM provider for critique generation.
            threshold: Minimum quality score to pass (0-100).
            max_rounds: Maximum self-correction rounds before accepting.
            temperature: LLM temperature for critic (lower = more consistent).
        """
        self.provider = provider
        self.threshold = threshold
        self.max_rounds = max_rounds
        self.temperature = temperature
        self._history: list[CritiqueResult] = []

    def evaluate(
        self,
        user_request: str,
        agent_output: str,
    ) -> CritiqueResult:
        """Evaluate agent output using the critic.

        Args:
            user_request: The original user request.
            agent_output: The agent's generated response.

        Returns:
            CritiqueResult with score, issues, and suggestions.
        """
        if not self.provider:
            # No provider — auto-approve with a basic heuristic check
            return self._heuristic_evaluate(agent_output)

        try:
            from nexus_agent.llm.base import Message, Role

            messages = [
                Message(role=Role.SYSTEM, content=CRITIC_SYSTEM_PROMPT),
                Message(
                    role=Role.USER,
                    content=_build_critic_prompt(user_request, agent_output),
                ),
            ]

            response = self.provider.chat_completion(
                messages=messages,
                tools=None,
                temperature=self.temperature,
                max_tokens=2048,
            )

            critique = _parse_critique_response(response.content or "")
            critique.approved = critique.score >= self.threshold
            self._history.append(critique)

            logger.info(
                f"Reflection critique: score={critique.score}, "
                f"approved={critique.approved}, issues={len(critique.issues)}"
            )

            return critique

        except (ValueError, RuntimeError) as e:
            logger.warning(f"Reflection evaluation failed: {e}")
            return CritiqueResult(
                score=60,
                approved=True,  # Don't block on evaluation failure
                summary=f"Evaluation error: {str(e)[:200]}",
            )

    def _heuristic_evaluate(self, output: str) -> CritiqueResult:
        """Basic heuristic evaluation when no LLM provider is available."""
        logger.info("Running heuristic evaluation (no LLM critic available)")
        issues: list[CritiqueIssue] = []
        score = 80

        # Check for empty or too-short responses
        if not output or len(output.strip()) < 20:
            issues.append(CritiqueIssue(
                category="completeness",
                severity="critical",
                description="Response is empty or extremely short",
            ))
            score -= 40

        # Check for error indicators
        error_indicators = ["Error:", "Failed:", "Exception:", "Traceback"]
        for indicator in error_indicators:
            if indicator in output:
                issues.append(CritiqueIssue(
                    category="correctness",
                    severity="major",
                    description=f"Response contains error indicator: '{indicator}'",
                ))
                score -= 15
                break

        # Check for placeholder content
        placeholder_indicators = ["TODO", "FIXME", "placeholder", "not implemented"]
        for indicator in placeholder_indicators:
            if indicator.lower() in output.lower():
                issues.append(CritiqueIssue(
                    category="completeness",
                    severity="minor",
                    description=f"Response contains placeholder: '{indicator}'",
                ))
                score -= 5

        score = max(0, min(100, score))

        logger.info(f"Heuristic evaluation complete: score={score}, issues={len(issues)}")

        return CritiqueResult(
            score=score,
            approved=score >= self.threshold,
            issues=issues,
            summary="Heuristic evaluation (no LLM critic available)",
        )

    def run_correction_loop(
        self,
        user_request: str,
        generate_fn: Callable[[str], str] | None = None,
        initial_output: str = "",
    ) -> tuple[str, list[CritiqueResult]]:
        """Run a full self-correction loop.

        Generates output, critiques it, and if below threshold,
        feeds the critique back for correction.

        Args:
            user_request: The original user request.
            generate_fn: Callable that takes (prompt) -> str to generate output.
            initial_output: Optional pre-generated output to start with.

        Returns:
            Tuple of (final_output, critique_history).
        """
        if generate_fn is None:
            return initial_output or "", []

        output = initial_output
        critiques: list[CritiqueResult] = []

        for round_num in range(self.max_rounds):
            if not output:
                output = generate_fn(user_request)

            critique = self.evaluate(user_request, output)
            critiques.append(critique)

            if critique.approved:
                logger.info(
                    f"Reflection passed at round {round_num + 1} "
                    f"with score {critique.score}"
                )
                break

            # Generate correction prompt
            if round_num < self.max_rounds - 1 and generate_fn:
                correction_prompt = (
                    f"{user_request}\n\n"
                    f"{critique.to_feedback_prompt()}\n\n"
                    f"Previous output:\n{output[:2000]}"
                )
                output = generate_fn(correction_prompt)
                logger.info(
                    f"Reflection round {round_num + 1}: score={critique.score}, "
                    f"regenerating..."
                )
            else:
                logger.info(
                    f"Reflection max rounds reached. "
                    f"Accepting output with score {critique.score}"
                )

        return output, critiques

    def get_history(self) -> list[CritiqueResult]:
        """Get the history of all critique results."""
        return list(self._history)

    def get_average_score(self) -> float:
        """Get the average quality score across all evaluations."""
        if not self._history:
            return 0.0
        return sum(c.score for c in self._history) / len(self._history)
