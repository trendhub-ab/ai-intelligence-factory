from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class XDiscoveryProvider(ABC):
    name = "unknown"
    external_calls = 0

    @abstractmethod
    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        raise NotImplementedError


class FixtureProvider(XDiscoveryProvider):
    name = "fixture"

    def __init__(self, fixture_path: Path):
        self.fixture_path = Path(fixture_path)
        self.external_calls = 0

    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("data", []))
        if not isinstance(payload, list):
            raise ValueError("fixture must contain a JSON array or an object with items/data")
        return [dict(item) for item in payload[:max_records] if isinstance(item, Mapping)]


class ApifyProvider(XDiscoveryProvider):
    name = "apify"

    def __init__(
        self,
        *,
        token: str,
        actor_id: str,
        actor_input: Optional[Mapping[str, Any]] = None,
        timeout_seconds: int = 120,
        max_total_charge_usd: float = 0.25,
    ):
        if not token.strip():
            raise ValueError("APIFY_TOKEN is required for live Apify runs")
        if not actor_id.strip():
            raise ValueError("APIFY_ACTOR_ID is required for live Apify runs")
        if not 1 <= int(timeout_seconds) <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not 0 < float(max_total_charge_usd) <= 1.0:
            raise ValueError("max_total_charge_usd must be > 0 and <= 1.0 for this PoC")
        self.token = token.strip()
        self.actor_id = actor_id.strip()
        self.actor_input = dict(actor_input or {})
        self.timeout_seconds = int(timeout_seconds)
        self.max_total_charge_usd = float(max_total_charge_usd)
        self.external_calls = 0

    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        if not 1 <= int(max_records) <= 100:
            raise ValueError("live Apify max_records must be between 1 and 100")

        actor = quote(self.actor_id, safe="~")
        query = urlencode(
            {
                "timeout": self.timeout_seconds,
                "maxItems": int(max_records),
                "maxTotalChargeUsd": self.max_total_charge_usd,
                "clean": "true",
                "format": "json",
            }
        )
        endpoint = f"https://api.apify.com/v2/actors/{actor}/run-sync-get-dataset-items?{query}"
        body = json.dumps(self.actor_input, ensure_ascii=False).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "ai-intelligence-factory-x-discovery/0.1",
            },
            method="POST",
        )
        self.external_calls += 1
        with urlopen(request, timeout=self.timeout_seconds + 15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("data", []))
        if not isinstance(payload, list):
            raise ValueError("Apify Actor response must be a JSON array or contain items/data")
        return [dict(item) for item in payload[:max_records] if isinstance(item, Mapping)]
