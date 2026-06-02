"""
Natural Language Autoencoder (NLA) Telemetry — Core logger and reasoning analysis utility.

Provides structured trace logging of agent thinking processes, strategy choices,
confidence ratings, and learning triggers to log files for architectural self-improvement.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NLARecord:
    """A structured log representing a single reasoning iteration."""
    timestamp: float
    thought_process: str
    strategy_selected: str
    tools_considered: list[str]
    confidence_score: float             # Value between 0.0 and 1.0
    alternative_paths: list[str]
    learning_signal: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NLATelemetry:
    """NLATelemetry captures, stores, and analyzes reasoning traces."""

    def __init__(self, session_id: str, workspace: Path | None = None, buffer_size: int = 10):
        """Initialize NLA Telemetry.

        Args:
            session_id: Unique session identifier.
            workspace: Root workspace directory.
            buffer_size: Number of records to buffer before writing to disk.
        """
        self.session_id = session_id
        self.workspace = workspace or Path.cwd()
        self.records: list[NLARecord] = []
        self._buffer: list[NLARecord] = []
        self._buffer_max_size = buffer_size

        # Setup logs directory
        self.logs_dir = self.workspace / ".nexus-agent" / "nla_logs"
        self.log_file = self.logs_dir / f"nla_{self.session_id}.jsonl"

    def log_iteration(
        self,
        thought_process: str,
        strategy_selected: str,
        tools_considered: list[str],
        confidence_score: float,
        alternative_paths: list[str],
        learning_signal: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NLARecord:
        """Create and write a structured reasoning log entry.

        Args:
            thought_process: The LLM thought process.
            strategy_selected: Selected action strategy.
            tools_considered: List of tools considered.
            confidence_score: Score 0.0 to 1.0.
            alternative_paths: Other paths that could have been chosen.
            learning_signal: Self-improvement signals.
            error_message: Any error message encountered.
            metadata: Extra key-value pairs.

        Returns:
            The recorded NLARecord.
        """
        record = NLARecord(
            timestamp=time.time(),
            thought_process=thought_process,
            strategy_selected=strategy_selected,
            tools_considered=tools_considered,
            confidence_score=max(0.0, min(1.0, confidence_score)),
            alternative_paths=alternative_paths,
            learning_signal=learning_signal,
            error_message=error_message,
            metadata=metadata or {},
        )
        self.records.append(record)
        self._buffer.append(record)

        if len(self._buffer) >= self._buffer_max_size:
            self.flush()

        return record

    def flush(self) -> None:
        """Flush buffered records to disk."""
        if not self._buffer:
            return
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            lines = "\n".join(json.dumps(r.to_dict()) for r in self._buffer) + "\n"
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(lines)
            self._buffer.clear()
        except (OSError, ValueError) as e:
            logger.error(f"Failed to flush NLA records: {e}")

    def load_records(self) -> list[NLARecord]:
        """Load all telemetry logs from disk for the current session.

        Parses each line individually to handle corrupt JSON lines gracefully.
        """
        if not self.log_file.exists():
            return []

        records = []
        try:
            with open(self.log_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        records.append(NLARecord(
                            timestamp=data.get("timestamp", time.time()),
                            thought_process=data.get("thought_process", ""),
                            strategy_selected=data.get("strategy_selected", ""),
                            tools_considered=data.get("tools_considered", []),
                            confidence_score=data.get("confidence_score", 1.0),
                            alternative_paths=data.get("alternative_paths", []),
                            learning_signal=data.get("learning_signal"),
                            error_message=data.get("error_message"),
                            metadata=data.get("metadata", {}),
                        ))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping corrupt JSON on line {line_num}: {e}")
            self.records = records
        except (OSError, ValueError) as e:
            logger.error(f"Failed to load NLA log records: {e}")
        return self.records

    def generate_session_summary(self) -> str:
        """Generate a human-readable Markdown summary of session reasoning logs."""
        records = self.load_records() if not self.records else self.records
        if not records:
            return "No reasoning telemetry recorded for this session."

        avg_confidence = sum(r.confidence_score for r in records) / len(records)
        strategies: dict[str, int] = {}
        errors: list[str] = []
        learning_signals: list[str] = []

        for r in records:
            strategies[r.strategy_selected] = strategies.get(r.strategy_selected, 0) + 1
            if r.error_message:
                errors.append(r.error_message)
            if r.learning_signal:
                learning_signals.append(r.learning_signal)

        lines = [
            "# 🧠 Natural Language Autoencoder Reasoning Summary",
            "",
            f"**Session ID:** `{self.session_id}`",
            f"**Total Reasoning Iterations:** {len(records)}",
            f"**Average Confidence Rating:** {avg_confidence * 100:.1f}%",
            "",
            "### 🚀 Strategy Execution Counts",
        ]

        for strat, count in strategies.items():
            lines.append(f"- `{strat}`: {count} times")

        if learning_signals:
            lines.extend([
                "",
                "### 💡 Architectural Learning Signals",
            ])
            for sig in learning_signals:
                lines.append(f"- {sig}")

        if errors:
            lines.extend([
                "",
                "### ⚠️ Errors Logged",
            ])
            for err in errors[-5:]:  # Last 5 errors
                lines.append(f"- `{err[:120]}`")

        lines.extend([
            "",
            "### 🔍 Detailed Step Telemetry",
        ])

        for idx, r in enumerate(records, 1):
            lines.extend([
                f"\n#### Iteration {idx} — Strategy: `{r.strategy_selected}` (Confidence: {r.confidence_score*100:.0f}%)",
                f"**Thought Process:** {r.thought_process[:250]}...",
                f"**Tools Considered:** {', '.join(f'`{t}`' for t in r.tools_considered)}",
            ])

        return "\n".join(lines)

    def export_training_pairs(self) -> list[dict[str, Any]]:
        """Extract input-output reflection pairs from successful runs for offline fine-tuning.

        Creates structural patterns useful for reinforcing the model's autoencoder reasoning.
        Redacts potentially sensitive content from training data.
        """
        records = self.load_records() if not self.records else self.records
        pairs = []

        # Redaction patterns for sensitive data
        _REDACT_PATTERNS = [
            (re.compile(r'(?i)(password|secret|api_key|token|credential)\s*[=:]\s*\S+'), r'\1=[REDACTED]'),
            (re.compile(r'(?i)(password|secret|api_key|token|credential)\s*["\']?\s*:\s*["\']?\S+'), r'\1: [REDACTED]'),
        ]

        for idx, r in enumerate(records):
            # Formulate training reflection pairs
            if r.confidence_score > 0.7:
                # Redact thought process and alternative paths
                redacted_thought = r.thought_process
                for pattern, replacement in _REDACT_PATTERNS:
                    redacted_thought = pattern.sub(replacement, redacted_thought)

                redacted_alternatives = [
                    pattern.sub(replacement, alt)
                    for alt in r.alternative_paths
                    for pattern, replacement in _REDACT_PATTERNS
                ]

                pairs.append({
                    "instruction": f"Formulate alternative strategy paths for solving tasks requiring tools: {', '.join(r.tools_considered)}",
                    "thought": redacted_thought,
                    "ideal_strategy": r.strategy_selected,
                    "alternatives": redacted_alternatives,
                })
        return pairs

    def get_error_patterns(self) -> dict[str, int]:
        """Analyze logs to discover recurring error pattern triggers."""
        records = self.load_records() if not self.records else self.records
        patterns: dict[str, int] = {}

        for r in records:
            if r.error_message:
                # Classify the error to strip variable paths/numbers
                clean_err = r.error_message.lower()
                clean_err = re.sub(r'[\/\\].*?\.[a-z0-9]+', '[FILE]', clean_err)
                clean_err = re.sub(r'\d+', '[NUM]', clean_err)
                patterns[clean_err] = patterns.get(clean_err, 0) + 1

        return patterns
