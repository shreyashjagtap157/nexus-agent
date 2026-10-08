"""Optional cached Models.dev-compatible provider/model catalog."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "https://models.dev/api.json"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


class ModelsDevCatalog:
    """Fetch and cache a provider/model catalog without storing credentials."""

    def __init__(
        self,
        cache_path: Path,
        url: str | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        self.cache_path = Path(cache_path)
        self.url = url or os.environ.get("NEXUS_MODELS_DEV_URL", DEFAULT_URL)
        self.ttl_seconds = max(60, int(ttl_seconds))

    def _read_cache(self) -> dict[str, Any] | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            fetched = float(payload.get("_nexus_fetched_at", 0))
            data = payload.get("data")
            if not isinstance(data, dict):
                return None
            payload["_fresh"] = (time.time() - fetched) <= self.ttl_seconds
            return payload
        except (OSError, ValueError, TypeError):
            return None

    def load(self, *, refresh: bool = False, timeout: float = 10.0) -> dict[str, Any]:
        cached = self._read_cache()
        if cached and cached.get("_fresh") and not refresh:
            return dict(cached["data"])

        if not refresh and cached:
            try:
                # A stale cache remains useful when the network is unavailable.
                if cached.get("data"):
                    return dict(cached["data"])
            except (TypeError, ValueError):
                pass

        response = httpx.get(
            self.url,
            timeout=max(1.0, timeout),
            follow_redirects=True,
            headers={"User-Agent": "NexusAgent/ModelsDevCatalog"},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Models.dev catalog response must be a JSON object.")

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_nexus_fetched_at": time.time(),
            "_nexus_source": self.url,
            "data": data,
        }
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return data

    def providers(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        data = self.load(refresh=refresh)
        rows: list[dict[str, Any]] = []
        for provider_id, value in data.items():
            if not isinstance(value, dict):
                continue
            row = dict(value)
            row.setdefault("id", provider_id)
            row["id"] = str(row["id"])
            rows.append(row)
        return sorted(rows, key=lambda item: str(item.get("id", "")).lower())

    def models(self, provider_id: str, *, refresh: bool = False) -> list[dict[str, Any]]:
        data = self.load(refresh=refresh)
        provider = data.get(provider_id)
        if not isinstance(provider, dict):
            return []
        models = provider.get("models", {})
        if not isinstance(models, dict):
            return []
        rows: list[dict[str, Any]] = []
        for model_id, value in models.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("id", model_id)
            else:
                row = {"id": model_id, "name": str(value)}
            row["id"] = str(row["id"])
            rows.append(row)
        return sorted(rows, key=lambda item: str(item.get("id", "")).lower())
