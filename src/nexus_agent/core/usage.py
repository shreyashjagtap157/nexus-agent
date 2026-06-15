"""
Usage Tracker — Aggregate token usage and estimated cost.

`UsageTracker` is a small JSON-file-backed counter that records one row
per LLM call (with `session_id`, `provider`, `model`, `prompt_tokens`,
`completion_tokens`, and a timestamp). Aggregations are computed on
demand for the `/cost` slash command.

Storage format (`.nexus/usage.json`):
{
  "version": 1,
  "entries": [
    {"ts": 1737000000.0, "session_id": "abc", "provider": "openai",
     "model": "gpt-4o", "prompt_tokens": 100, "completion_tokens": 50,
     "estimated_cost": 0.001},
    ...
  ]
}

We keep an append-only log (with periodic compaction) so that a crash
mid-write doesn't corrupt the file.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (USD). Editable; defaults are conservative mid-2024 rates.
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # provider/model: {"input": $/1M input, "output": $/1M output}
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "default": {"input": 2.50, "output": 10.00},
    },
    "anthropic": {
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
        "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
        "default": {"input": 3.00, "output": 15.00},
    },
    "google": {
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "default": {"input": 1.25, "output": 5.00},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.27, "output": 1.10},
        "default": {"input": 0.27, "output": 1.10},
    },
    "groq": {
        "default": {"input": 0.10, "output": 0.30},
    },
    "ollama": {"default": {"input": 0.0, "output": 0.0}},
    "openrouter": {"default": {"input": 5.0, "output": 15.0}},
    "bedrock": {"default": {"input": 3.0, "output": 15.0}},
    "local": {"default": {"input": 0.0, "output": 0.0}},
}


def estimate_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: dict[str, dict[str, float]] | None = None,
) -> float:
    """Estimate cost in USD for one LLM call."""
    p = pricing or DEFAULT_PRICING
    table = p.get((provider or "").lower(), p.get("default", {}))
    rates = table.get(model or "") or table.get("default", {"input": 0.0, "output": 0.0})
    cost_in = (max(0, prompt_tokens) / 1_000_000.0) * rates.get("input", 0.0)
    cost_out = (max(0, completion_tokens) / 1_000_000.0) * rates.get("output", 0.0)
    return round(cost_in + cost_out, 6)


@dataclass
class UsageEntry:
    ts: float
    session_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float = 0.0
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UsageEntry:
        return cls(
            ts=_safe_float(data.get("ts", 0.0), 0.0),
            session_id=str(data.get("session_id", "")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            prompt_tokens=_safe_int(data.get("prompt_tokens", 0), 0),
            completion_tokens=_safe_int(data.get("completion_tokens", 0), 0),
            estimated_cost=_safe_float(data.get("estimated_cost", 0.0), 0.0),
            label=str(data.get("label", "")),
        )


@dataclass
class UsageSummary:
    """Aggregated usage stats."""

    entries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    by_session: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_day: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_lines(self, *, top_n: int = 5) -> list[str]:
        lines = [
            f"Entries: {self.entries}",
            f"Prompt tokens:     {self.prompt_tokens:>10,}",
            f"Completion tokens: {self.completion_tokens:>10,}",
            f"Total tokens:      {self.total_tokens:>10,}",
            f"Estimated cost:    ${self.estimated_cost:.4f}",
        ]
        if self.by_model:
            lines.append("")
            lines.append(f"By model (top {top_n}):")
            for m, s in list(self.by_model.items())[:top_n]:
                lines.append(
                    f"  {m[:40]:<40}  {s['total_tokens']:>10,} tok  ${s['estimated_cost']:.4f}"
                )
        if self.by_session:
            lines.append("")
            lines.append(f"By session (top {top_n}):")
            for sid, s in list(self.by_session.items())[:top_n]:
                lines.append(
                    f"  {sid[:40]:<40}  {s['total_tokens']:>10,} tok  ${s['estimated_cost']:.4f}"
                )
        if self.by_day:
            lines.append("")
            lines.append(f"By day (top {top_n}):")
            for day, s in list(self.by_day.items())[:top_n]:
                lines.append(
                    f"  {day}  {s['total_tokens']:>10,} tok  ${s['estimated_cost']:.4f}"
                )
        return lines


def _day_key(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class UsageTracker:
    """Append-only JSON file usage tracker."""

    SCHEMA_VERSION = 1
    MAX_ENTRIES_BEFORE_COMPACT = 5000

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._entries: list[UsageEntry] = []
        if path is not None:
            self._load()

    # ---- persistence ----

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"UsageTracker: failed to read {self.path}: {e}")
            return
        version = data.get("version", 1)
        if version > self.SCHEMA_VERSION:
            logger.warning(
                f"UsageTracker: file schema version {version} > supported "
                f"{self.SCHEMA_VERSION}; ignoring contents."
            )
            return
        self._entries = [UsageEntry.from_dict(e) for e in data.get("entries", [])]

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": self.SCHEMA_VERSION,
                "saved_at": time.time(),
                "entries": [e.to_dict() for e in self._entries],
            }
            # Atomic write — write to a temp file in the same directory
            # then replace. Avoids partial writes on crash.
            fd, tmp = tempfile.mkstemp(
                prefix=".usage.", suffix=".json.tmp", dir=self.path.parent
            )
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=1, sort_keys=True)
                Path(tmp).replace(self.path)
            except (OSError, ValueError) as e:
                logger.warning(f"UsageTracker: failed to write {self.path}: {e}")
                try:
                    Path(tmp).unlink(missing_ok=True)
                except OSError:
                    pass
        except OSError as e:
            logger.warning(f"UsageTracker: failed to save: {e}")

    # ---- recording ----

    def record(
        self,
        *,
        session_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        label: str = "",
        pricing: dict[str, dict[str, float]] | None = None,
    ) -> UsageEntry:
        """Append one usage entry, returning it."""
        cost = estimate_cost(
            provider, model, prompt_tokens, completion_tokens, pricing
        )
        entry = UsageEntry(
            ts=time.time(),
            session_id=session_id or "unknown",
            provider=provider or "",
            model=model or "",
            prompt_tokens=max(0, int(prompt_tokens or 0)),
            completion_tokens=max(0, int(completion_tokens or 0)),
            estimated_cost=cost,
            label=label or "",
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.MAX_ENTRIES_BEFORE_COMPACT:
                self._compact_locked()
            self._save()
        return entry

    def _compact_locked(self) -> None:
        """Drop entries older than 30 days, keeping at least 1000."""
        cutoff = time.time() - 30 * 24 * 3600
        if len(self._entries) <= 1000:
            return
        recent = [e for e in self._entries if e.ts >= cutoff]
        # If we still have many recent, drop the oldest beyond 1000.
        if len(recent) > 1000:
            recent = recent[-1000:]
        self._entries = recent

    # ---- queries ----

    def entries(self) -> list[UsageEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries = []
            self._save()
        return n

    def clear_session(self, session_id: str) -> int:
        with self._lock:
            n_before = len(self._entries)
            self._entries = [
                e for e in self._entries if e.session_id != session_id
            ]
            removed = n_before - len(self._entries)
            if removed:
                self._save()
        return removed

    def summarize(
        self,
        *,
        session_id: str | None = None,
        since_ts: float | None = None,
        until_ts: float | None = None,
    ) -> UsageSummary:
        """Return aggregated stats, optionally filtered."""
        with self._lock:
            entries = self._filter_locked(session_id, since_ts, until_ts)
            return self._aggregate(entries)

    def _filter_locked(
        self,
        session_id: str | None,
        since_ts: float | None,
        until_ts: float | None,
    ) -> list[UsageEntry]:
        out: list[UsageEntry] = []
        for e in self._entries:
            if session_id is not None and e.session_id != session_id:
                continue
            if since_ts is not None and e.ts < since_ts:
                continue
            if until_ts is not None and e.ts > until_ts:
                continue
            out.append(e)
        return out

    @staticmethod
    def _aggregate(entries: Iterable[UsageEntry]) -> UsageSummary:
        s = UsageSummary()
        for e in entries:
            s.entries += 1
            s.prompt_tokens += e.prompt_tokens
            s.completion_tokens += e.completion_tokens
            s.total_tokens += e.prompt_tokens + e.completion_tokens
            s.estimated_cost += e.estimated_cost

            sess = s.by_session.setdefault(
                e.session_id,
                {"prompt_tokens": 0, "completion_tokens": 0,
                 "total_tokens": 0, "estimated_cost": 0.0, "entries": 0},
            )
            sess["prompt_tokens"] += e.prompt_tokens
            sess["completion_tokens"] += e.completion_tokens
            sess["total_tokens"] += e.prompt_tokens + e.completion_tokens
            sess["estimated_cost"] += e.estimated_cost
            sess["entries"] += 1

            model_key = f"{e.provider}/{e.model}" if e.provider else e.model or "unknown"
            m = s.by_model.setdefault(
                model_key,
                {"prompt_tokens": 0, "completion_tokens": 0,
                 "total_tokens": 0, "estimated_cost": 0.0, "entries": 0},
            )
            m["prompt_tokens"] += e.prompt_tokens
            m["completion_tokens"] += e.completion_tokens
            m["total_tokens"] += e.prompt_tokens + e.completion_tokens
            m["estimated_cost"] += e.estimated_cost
            m["entries"] += 1

            day = _day_key(e.ts)
            d = s.by_day.setdefault(
                day,
                {"prompt_tokens": 0, "completion_tokens": 0,
                 "total_tokens": 0, "estimated_cost": 0.0, "entries": 0},
            )
            d["prompt_tokens"] += e.prompt_tokens
            d["completion_tokens"] += e.completion_tokens
            d["total_tokens"] += e.prompt_tokens + e.completion_tokens
            d["estimated_cost"] += e.estimated_cost
            d["entries"] += 1

        s.estimated_cost = round(s.estimated_cost, 6)
        # Sort breakdowns by cost descending.
        s.by_model = dict(
            sorted(s.by_model.items(), key=lambda kv: -kv[1]["estimated_cost"])
        )
        s.by_session = dict(
            sorted(s.by_session.items(), key=lambda kv: -kv[1]["estimated_cost"])
        )
        s.by_day = dict(
            sorted(s.by_day.items(), key=lambda kv: kv[0], reverse=True)
        )
        return s
