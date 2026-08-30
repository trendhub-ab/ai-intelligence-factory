#!/usr/bin/env python3
"""Live schema contract guard for Content Intelligence DB. ZERO model calls."""
from __future__ import annotations

import json
import sys
from typing import Any

import requests

import pipeline as p

SOURCE_VALUES = {"GitHub", "HackerNews", "ArXiv", "ProductHunt"}
CONTENT_STATUS_VALUES = {
    p.CONTENT_STATUS_STOCKED,
    p.CONTENT_STATUS_DEEP_DIVE,
    p.CONTENT_STATUS_QUALITY_FAILED,
    p.CONTENT_STATUS_PENDING_RETRY,
}
ARTICLE_STATUS_VALUES = {
    p.ARTICLE_STATUS_NOT_PLANNED,
    p.ARTICLE_STATUS_READY,
    p.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
}
VISIBILITY_VALUES = {
    p.VISIBILITY_SUBSCRIBER_ONLY,
    p.VISIBILITY_PAID_ARTICLE,
    p.VISIBILITY_FREE_ARTICLE,
}
GROUNDING_VALUES = {
    p.GROUNDING_METADATA_ONLY,
    p.GROUNDING_SOURCE_NATIVE,
    p.GROUNDING_URL_CONTEXT,
    p.GROUNDING_URL_SEARCH,
    p.GROUNDING_FAILED,
}

ENUM_CONTRACTS = {
    p.PROP_SOURCE: SOURCE_VALUES,
    p.PROP_STATUS: {p.STATUS_STOCKED, p.STATUS_DEEP_DIVE},
    p.PROP_CONTENT_STATUS: CONTENT_STATUS_VALUES,
    p.PROP_ARTICLE_STATUS: ARTICLE_STATUS_VALUES,
    p.PROP_SUBSCRIPTION_VISIBILITY: VISIBILITY_VALUES,
    p.PROP_DECISION: set(p.ALLOWED_DECISIONS),
    p.PROP_GROUNDING_STATUS: GROUNDING_VALUES,
}


def option_names(prop: dict[str, Any] | None) -> set[str]:
    prop = prop or {}
    kind = str(prop.get("type") or "")
    if kind not in {"select", "multi_select", "status"}:
        return set()
    if kind == "status":
        groups = (prop.get("status") or {}).get("groups") or prop.get("groups") or {}
        if isinstance(groups, dict):
            return {
                str(item.get("name") or "").strip()
                for items in groups.values()
                for item in (items or [])
                if str(item.get("name") or "").strip()
            }
    return {
        str(item.get("name") or "").strip()
        for item in ((prop.get(kind) or {}).get("options") or [])
        if str(item.get("name") or "").strip()
    }


def validate_enum_contracts(properties: dict[str, Any]) -> None:
    failures: dict[str, list[str]] = {}
    for name, required in ENUM_CONTRACTS.items():
        prop = properties.get(name) or {}
        if prop.get("type") != "select":
            failures[name] = [f"wrong_type:{prop.get('type') or 'missing'}"]
            continue
        missing = sorted(set(required) - option_names(prop))
        if missing:
            failures[name] = missing
    if failures:
        raise ValueError(
            "Content Intelligence enum contract incompatible: "
            + "; ".join(f"{name} missing={','.join(values)}" for name, values in failures.items())
        )


def run() -> dict[str, Any]:
    if not p.NOTION_API_KEY or not (p.NOTION_DATA_SOURCE_ID or p.NOTION_DATABASE_ID):
        return {"enabled": False, "zero_gemini_calls": True}
    p.preflight_notion_schema()
    schema_url = (
        f"https://api.notion.com/v1/data_sources/{p.NOTION_DATA_SOURCE_ID}"
        if p.NOTION_DATA_SOURCE_ID
        else f"https://api.notion.com/v1/databases/{p.NOTION_DATABASE_ID}"
    )
    response = requests.get(schema_url, headers=p._notion_headers(), timeout=15)
    response.raise_for_status()
    properties = response.json().get("properties") or {}
    validate_enum_contracts(properties)
    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "required_property_types": "ok",
        "enum_contracts": "ok",
    }


def main(argv: list[str] | None = None) -> int:
    if list(argv if argv is not None else sys.argv[1:]):
        raise SystemExit("usage: python content_db_contract_guard.py")
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
