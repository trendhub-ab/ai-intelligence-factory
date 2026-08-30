#!/usr/bin/env python3
"""Live schema contract guard for the Evidence Ledger. ZERO model calls."""
from __future__ import annotations

import json
import sys
from typing import Any

import requests

import decision_intelligence as di
import evidence_ledger as el


def option_names(prop: dict[str, Any] | None) -> set[str]:
    prop = prop or {}
    kind = str(prop.get("type") or "")
    if kind not in {"select", "multi_select", "status"}:
        return set()
    return {
        str(x.get("name") or "").strip()
        for x in ((prop.get(kind) or {}).get("options") or [])
        if str(x.get("name") or "").strip()
    }


def validate_health_options(properties: dict[str, Any]) -> None:
    prop = properties.get(el.P_HEALTH) or {}
    if prop.get("type") != "select":
        raise ValueError(f"Evidence Ledger {el.P_HEALTH} must be select")
    missing = sorted(set(el.HEALTH_VALUES) - option_names(prop))
    if missing:
        raise ValueError(f"Evidence Ledger source-health contract missing: {','.join(missing)}")


def run() -> dict[str, Any]:
    if not el.ENABLE_EVIDENCE_LEDGER:
        return {"enabled": False, "zero_gemini_calls": True}
    token = di.NOTION_DECISION_INTELLIGENCE_API_KEY
    if not token:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    el.preflight(token)
    response = requests.get(el._schema_url(), headers=el._headers(token), timeout=15)
    response.raise_for_status()
    props = response.json().get("properties") or {}
    validate_health_options(props)
    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "required_property_types": "ok",
        "source_health_options": "ok",
    }


def main(argv: list[str] | None = None) -> int:
    if list(argv if argv is not None else sys.argv[1:]):
        raise SystemExit("usage: python evidence_db_contract_guard.py")
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
