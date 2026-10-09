"""Persistent user-configurable research source registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ResearchSource:
    id: str
    url: str
    name: str = ""
    source_type: str = "web"
    priority: int = 50
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchSourceRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[ResearchSource]:
        if not self.path.exists():
            return []
        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return []
        raw = data.get("sources", []) if isinstance(data, dict) else []
        result = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("id") or not item.get("url"):
                continue
            result.append(
                ResearchSource(
                    id=str(item["id"]).strip().lower(),
                    url=str(item["url"]).strip(),
                    name=str(item.get("name") or "").strip(),
                    source_type=str(item.get("source_type") or "web").strip(),
                    priority=int(item.get("priority", 50)),
                    enabled=bool(item.get("enabled", True)),
                    tags=[str(x).strip() for x in item.get("tags", []) if str(x).strip()],
                    notes=str(item.get("notes") or ""),
                )
            )
        return result

    def _write(self, sources: list[ResearchSource]) -> None:
        payload = {
            "sources": [
                item.to_dict() for item in sorted(sources, key=lambda x: (-x.priority, x.id))
            ]
        }
        self.path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def list(self, enabled_only: bool = False) -> list[ResearchSource]:
        sources = self._read()
        return [item for item in sources if item.enabled] if enabled_only else sources

    def get(self, source_id: str) -> ResearchSource | None:
        key = source_id.strip().lower()
        return next((item for item in self._read() if item.id == key), None)

    def add(self, source: ResearchSource) -> ResearchSource:
        if not source.id or not source.url:
            raise ValueError("Research source requires id and url.")
        sources = [item for item in self._read() if item.id != source.id]
        sources.append(source)
        self._write(sources)
        return source

    def remove(self, source_id: str) -> bool:
        key = source_id.strip().lower()
        sources = self._read()
        remaining = [item for item in sources if item.id != key]
        changed = len(remaining) != len(sources)
        if changed:
            self._write(remaining)
        return changed

    def seed_urls(self, urls: list[str]) -> int:
        added = 0
        for url in urls:
            clean = url.strip()
            if not clean:
                continue
            import hashlib

            identifier = "source-" + hashlib.sha1(clean.encode("utf-8")).hexdigest()[:12]
            self.add(ResearchSource(id=identifier, url=clean, name=clean))
            added += 1
        return added
