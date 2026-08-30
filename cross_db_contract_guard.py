#!/usr/bin/env python3
"""Cross-DB contract guard for Decision Intelligence.

This module protects the boundaries between the internal Technology DB, append-only
History DB, subscriber bridge, and the clean member presentation DB.

Why this exists:
- Notion schema preflight historically checked property names/types only.
- A SELECT/MULTI_SELECT property can therefore exist with the correct type while
  still missing a value that production code is allowed to write.
- Member-facing completeness must be validated after presentation fallbacks have
  run, not only at the internal/source layer.

The guard is deterministic and makes ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Iterable

import requests

import decision_intelligence as di
import member_presentation_sync as mps


SOURCE_OPTIONS = {"GitHub", "HackerNews", "ArXiv", "ProductHunt", "Unknown"}
CATEGORY_OPTIONS = {
    "MODEL",
    "AGENT",
    "DEVTOOLS",
    "INFRA",
    "DATA",
    "SECURITY",
    "MULTIMODAL",
    "PRODUCT",
    "OTHER",
}
MEMBER_CATEGORY_OPTIONS = {
    "AIモデル",
    "エージェント",
    "開発ツール",
    "基盤",
    "データ",
    "セキュリティ",
    "マルチモーダル",
    "製品・サービス",
    "その他",
}
PIPELINE_STATUS_OPTIONS = {"Stocked", "Deep Dive", "Product Review", "External Review Import"}
CONTENT_STATUS_OPTIONS = {"Stocked", "Pending Retry", "Quality Failed", "Deep Dive"}
ARTICLE_STATUS_OPTIONS = {"Not Planned", "Needs Editorial Review", "Ready"}

TECH_ENUM_CONTRACTS: dict[str, set[str]] = {
    di.TECH_PROP_SOURCE: SOURCE_OPTIONS,
    di.TECH_PROP_CATEGORY: CATEGORY_OPTIONS,
    di.TECH_PROP_ADOPTION_STATUS: set(di.ADOPTION_STATUSES),
    di.TECH_PROP_EVIDENCE_CONFIDENCE: set(di.CONFIDENCE_LEVELS),
    di.TECH_PROP_PRODUCTION_READINESS: set(di.READINESS_LEVELS),
    di.TECH_PROP_ENTITY_STATUS: set(di.ENTITY_RESOLUTION_STATUSES),
    di.TECH_PROP_TRACKING_STATUS: set(di.TRACKING_STATUSES),
    di.TECH_PROP_ASSESSMENT_STATE: set(di.ASSESSMENT_STATES),
    di.TECH_PROP_PIPELINE_STATUS: PIPELINE_STATUS_OPTIONS,
    di.TECH_PROP_CONTENT_STATUS: CONTENT_STATUS_OPTIONS,
    di.TECH_PROP_ARTICLE_STATUS: ARTICLE_STATUS_OPTIONS,
}

HISTORY_ENUM_CONTRACTS: dict[str, set[str]] = {
    di.HISTORY_PROP_ADOPTION_STATUS: set(di.ADOPTION_STATUSES),
    di.HISTORY_PROP_PREVIOUS_STATUS: set(di.ADOPTION_STATUSES),
    di.HISTORY_PROP_PRODUCTION_READINESS: set(di.READINESS_LEVELS),
    di.HISTORY_PROP_EVIDENCE_CONFIDENCE: set(di.CONFIDENCE_LEVELS),
    di.HISTORY_PROP_SNAPSHOT_TYPE: set(di.SNAPSHOT_TYPES),
}

SUBSCRIBER_ENUM_CONTRACTS: dict[str, set[str]] = {
    di.SUB_PROP_SOURCE: SOURCE_OPTIONS,
    di.SUB_PROP_CATEGORY: CATEGORY_OPTIONS,
    di.SUB_PROP_ADOPTION_STATUS: set(di.ADOPTION_STATUSES),
    di.SUB_PROP_EVIDENCE_CONFIDENCE: set(di.CONFIDENCE_LEVELS),
    di.SUB_PROP_PRODUCTION_READINESS: set(di.READINESS_LEVELS),
}

MEMBER_ENUM_CONTRACTS: dict[str, set[str]] = {
    "判断": set(di.ADOPTION_STATUSES),
    "根拠の確かさ": {"高", "中", "低"},
    "実用度": {"高", "中", "低"},
    "分野": MEMBER_CATEGORY_OPTIONS,
    "分類": {"実務判断", "Deep Tech", "参考資料"},
    "情報源": SOURCE_OPTIONS,
}

MEMBER_REQUIRED_TEXT_FIELDS = (
    "sync_id",
    "name",
    "plain_summary",
    "status",
    "judgment_reason",
    "topic",
    "next_action",
    "evidence",
    "confidence",
    "readiness",
    "category",
    "classification",
)


def _option_names(prop: dict[str, Any] | None) -> set[str]:
    """Return Notion API SELECT/MULTI_SELECT option names from a schema property."""
    prop = prop or {}
    prop_type = str(prop.get("type") or "")
    if prop_type not in {"select", "multi_select", "status"}:
        return set()
    options = ((prop.get(prop_type) or {}).get("options") or [])
    return {
        str(option.get("name") or "").strip()
        for option in options
        if str(option.get("name") or "").strip()
    }


def validate_enum_contracts(
    properties: dict[str, Any],
    contracts: dict[str, set[str]],
    label: str,
) -> dict[str, list[str]]:
    """Fail if production-supported enum values are absent from the Notion schema."""
    failures: dict[str, list[str]] = {}
    for property_name, required in contracts.items():
        prop = properties.get(property_name) or {}
        actual_type = str(prop.get("type") or "")
        if actual_type not in {"select", "multi_select", "status"}:
            failures[property_name] = [f"wrong_type:{actual_type or 'missing'}"]
            continue
        missing = sorted(set(required) - _option_names(prop))
        if missing:
            failures[property_name] = missing
    if failures:
        detail = "; ".join(
            f"{name} missing={','.join(values)}" for name, values in failures.items()
        )
        raise ValueError(f"{label} enum contract incompatible: {detail}")
    return failures


def _fetch_schema(data_source_id: str, database_id: str, label: str) -> dict[str, Any]:
    response = requests.get(
        di._schema_url(data_source_id, database_id),
        headers=di._headers(),
        timeout=15,
    )
    response.raise_for_status()
    properties = response.json().get("properties") or {}
    if not isinstance(properties, dict):
        raise ValueError(f"{label} schema response has no properties map")
    return properties


def run_schema_contracts() -> dict[str, Any]:
    """Validate property types plus all enum values that production can write."""
    if not di.ENABLE_DECISION_INTELLIGENCE_DB:
        return {"enabled": False, "zero_gemini_calls": True, "checked": []}

    # Existing preflight remains the source of truth for required property names/types.
    di.preflight_decision_intelligence_schema()

    tech = _fetch_schema(di.NOTION_TECH_DATA_SOURCE_ID, di.NOTION_TECH_DATABASE_ID, "Technology Intelligence DB")
    history = _fetch_schema(di.NOTION_HISTORY_DATA_SOURCE_ID, di.NOTION_HISTORY_DATABASE_ID, "Decision History DB")
    validate_enum_contracts(tech, TECH_ENUM_CONTRACTS, "Technology Intelligence DB")
    validate_enum_contracts(history, HISTORY_ENUM_CONTRACTS, "Decision History DB")
    checked = ["Technology Intelligence DB", "Decision History DB"]

    if di.ENABLE_SUBSCRIBER_TECH_SYNC:
        subscriber = _fetch_schema(
            di.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID,
            di.NOTION_SUBSCRIBER_TECH_DATABASE_ID,
            "Subscriber Technology DB",
        )
        validate_enum_contracts(subscriber, SUBSCRIBER_ENUM_CONTRACTS, "Subscriber Technology DB")
        checked.append("Subscriber Technology DB")

    # Monthly has no enum-valued fields; di.preflight_decision_intelligence_schema()
    # already validates all of its required property names/types when enabled.
    if di.ENABLE_DECISION_MONTHLY_DIGEST:
        checked.append("Decision Monthly DB")

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "checked": checked,
        "enum_contracts": "ok",
    }


def validate_member_states(states: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fail closed if a clean member row lacks a core decision/explanation field."""
    failures: list[dict[str, Any]] = []
    duplicate_sync_ids: set[str] = set()
    seen: set[str] = set()
    count = 0

    for state in states:
        count += 1
        sync_id = str(state.get("sync_id") or "").strip()
        if sync_id:
            if sync_id in seen:
                duplicate_sync_ids.add(sync_id)
            seen.add(sync_id)

        missing = [
            field
            for field in MEMBER_REQUIRED_TEXT_FIELDS
            if not str(state.get(field) or "").strip()
        ]
        score = state.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            missing.append("score")
        if missing:
            failures.append(
                {
                    "sync_id": sync_id,
                    "name": str(state.get("name") or "").strip(),
                    "missing": sorted(set(missing)),
                }
            )

    if duplicate_sync_ids or failures:
        sample = failures[:10]
        raise ValueError(
            "Member presentation contract failed: "
            f"duplicates={sorted(duplicate_sync_ids)} failures={json.dumps(sample, ensure_ascii=False)}"
        )
    return {"records": count, "missing_core_fields": 0, "duplicate_sync_ids": 0}


def run_member_contract() -> dict[str, Any]:
    """Read the clean presentation DB after sync and verify schema + member content."""
    if not di.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    if not (mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID or mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID):
        raise ValueError("Member presentation DB is not configured")

    schema = _fetch_schema(
        mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
        mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID,
        "Member Presentation DB",
    )
    validate_enum_contracts(schema, MEMBER_ENUM_CONTRACTS, "Member Presentation DB")

    pages = di._query_external_db(
        mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
        mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID,
        max_records=5000,
    )
    states = [mps._destination_state(page) for page in pages]
    result = validate_member_states(states)
    result.update({"enabled": True, "zero_gemini_calls": True, "enum_contracts": "ok"})
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"schemas", "member"}:
        raise SystemExit("usage: python cross_db_contract_guard.py [schemas|member]")
    result = run_schema_contracts() if args[0] == "schemas" else run_member_contract()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
