#!/usr/bin/env python3
"""Read-only health probe for the canonical paid-member Notion data source."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

import decision_intelligence

DATA_SOURCE_ID = os.environ.get(
    "NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID",
    "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404",
).strip()
REQUEST_TIMEOUT_SECONDS = max(
    1.0, float(os.environ.get("MEMBER_NOTION_HEALTH_TIMEOUT_SECONDS", "10"))
)


def check_health() -> dict[str, Any]:
    if not decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    if not DATA_SOURCE_ID:
        raise ValueError("NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID is required")

    started = time.monotonic()
    try:
        response = requests.get(
            f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}",
            headers=decision_intelligence._headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        elapsed_ms = round((time.monotonic() - started) * 1000)
        response_elapsed = getattr(getattr(response, "elapsed", None), "total_seconds", None)
        if callable(response_elapsed):
            try:
                elapsed_ms = round(float(response_elapsed()) * 1000)
            except (TypeError, ValueError):
                pass
        return {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "http_status": int(response.status_code),
            "elapsed_ms": elapsed_ms,
            "method": "GET",
            "writes": False,
            "gemini_calls": 0,
        }
    except requests.RequestException as exc:
        return {
            "status": "unhealthy",
            "http_status": None,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "method": "GET",
            "writes": False,
            "gemini_calls": 0,
            "transport_error": type(exc).__name__,
        }


def main() -> int:
    result = check_health()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
