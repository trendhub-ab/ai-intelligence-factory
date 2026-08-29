#!/usr/bin/env python3
"""Run132 Context-First enrichment for Decision Intelligence.

This module adds the reader-facing context that should come before a score or
recommendation and maintains a durable member-facing change highlight:

- Plain Summary  -> member formula: 「これは何？」
- Topic Trigger  -> member formula: 「今回の話題」
- 「重要変化スコア」「重要変化日」「重要変化理由」 -> durable member change display

Design constraints:
- ZERO Gemini requests. It only reuses already-persisted Product Review state and
  append-only Decision History.
- Never changes Adoption/Evidence/History semantics.
- Never clears a subscriber value when the internal/history value is blank.
- Preserve existing human-curated member copy. Plain Summary is only filled when
  missing; Topic Trigger is refreshed only after an actual Product Review.
- A later no-change review must never erase an earlier meaningful score movement.
- Within the current product month, keep the largest meaningful score movement so
  a later smaller/no-change review cannot hide a major movement from members.
- Fail closed when the required Notion properties are missing, so a Daily run
  cannot silently produce context-less or change-less member inventory.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

import decision_intelligence


TECH_PROP_PLAIN_SUMMARY = "Plain Summary"
TECH_PROP_TOPIC_TRIGGER = "Topic Trigger"
SUB_PROP_PLAIN_SUMMARY = "Plain Summary"
SUB_PROP_TOPIC_TRIGGER = "Topic Trigger"
SUB_PROP_MEMBER_SCORE_CHANGE = "重要変化スコア"
SUB_PROP_MEMBER_CHANGE_AT = "重要変化日"
SUB_PROP_MEMBER_CHANGE_REASON = "重要変化理由"

_CATEGORY_SUMMARY = {
    "MODEL": "{name}は、文章生成や推論などに使われるAIモデル・モデル技術です。",
    "AGENT": "{name}は、複数の処理や判断を自律的に進めるAIエージェント関連技術です。",
    "DEVTOOLS": "{name}は、AIやソフトウェア開発を支援する開発ツールです。",
    "INFRA": "{name}は、AIシステムの実行・運用を支える基盤技術です。",
    "DATA": "{name}は、AIで使うデータの収集・処理・管理を支える技術です。",
    "SECURITY": "{name}は、AIやソフトウェアの安全性を高めるセキュリティ技術です。",
    "MULTIMODAL": "{name}は、テキスト・画像・音声など複数種類の情報を扱うAI技術です。",
    "PRODUCT": "{name}は、AIを利用した製品・サービスです。",
    "OTHER": "{name}は、AI活用やソフトウェアに関わる技術・プロジェクトです。",
}


def _text(prop: dict | None) -> str:
    """Read a Notion title/rich_text/formula string without network side effects."""
    prop = prop or {}
    for key in ("rich_text", "title"):
        values = prop.get(key) or []
        if values:
            return "".join(
                str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "")
                for x in values
            ).strip()
    formula = prop.get("formula") or {}
    if isinstance(formula.get("string"), str):
        return formula["string"].strip()
    return ""


def _select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _date(prop: dict | None) -> str | None:
    return ((prop or {}).get("date") or {}).get("start")


def _number(prop: dict | None) -> int | float | None:
    value = (prop or {}).get("number")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rt(value: str) -> dict:
    value = str(value or "").strip()[:2000]
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": value}}]}


def _date_prop(value: str | None) -> dict:
    return {"date": {"start": value}} if value else {"date": None}


def _number_prop(value: int | float | None) -> dict:
    return {"number": value if isinstance(value, (int, float)) and not isinstance(value, bool) else None}


def _clean_sentence(value: str, *, limit: int = 260) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    value = re.sub(r"^[・\-–—:：\s]+", "", value)
    if not value:
        return ""
    if len(value) > limit:
        cut = max(
            value.rfind("。", 0, limit + 1),
            value.rfind("！", 0, limit + 1),
            value.rfind("？", 0, limit + 1),
        )
        if cut >= max(40, limit // 2):
            value = value[: cut + 1]
        else:
            value = value[: limit - 1].rstrip("、,。.!！?？ ") + "。"
    if value[-1] not in "。.!！?？":
        value += "。"
    return value


def _display_description(label: str, name: str) -> str:
    """Extract the descriptive half of `Name — Japanese explanation` labels."""
    label = re.sub(r"\s+", " ", str(label or "")).strip()
    if not label:
        return ""
    for separator in (" — ", " – ", " - ", "：", ":"):
        if separator in label:
            _left, right = label.split(separator, 1)
            right = right.strip()
            if right and right.casefold() != str(name or "").strip().casefold():
                return _clean_sentence(right, limit=220)
    if label.casefold() != str(name or "").strip().casefold() and len(label) >= 12:
        return _clean_sentence(label, limit=220)
    return ""


def derive_plain_summary(state: dict[str, Any]) -> str:
    """Create a non-engineer-friendly definition without inventing product claims."""
    existing = str(state.get("plain_summary") or "").strip()
    if existing:
        return existing

    name = str(state.get("technology_name") or state.get("name") or "この技術").strip() or "この技術"
    from_label = _display_description(str(state.get("japanese_display_label") or ""), name)
    if from_label:
        return from_label

    category = str(state.get("category") or "OTHER").strip().upper()
    template = _CATEGORY_SUMMARY.get(category, _CATEGORY_SUMMARY["OTHER"])
    return _clean_sentence(template.format(name=name), limit=220)


def derive_topic_trigger(state: dict[str, Any]) -> str:
    """Explain why the item is being looked at now without fabricating breaking news."""
    rationale = _clean_sentence(str(state.get("short_rationale") or ""), limit=220)
    if rationale:
        return _clean_sentence(f"今回の確認では、{rationale}", limit=260)

    screening = _clean_sentence(str(state.get("screening_reason") or ""), limit=200)
    if screening:
        return _clean_sentence(f"今回取り上げた理由は、{screening}", limit=240)

    name = str(state.get("technology_name") or state.get("name") or "この技術").strip() or "この技術"
    return _clean_sentence(
        f"{name}について、現在の導入判断とその根拠を確認するために今回取り上げています",
        limit=240,
    )


def _page_state(page: dict) -> dict[str, Any]:
    props = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or ""),
        "technology_name": _text(props.get(decision_intelligence.TECH_PROP_NAME)),
        "japanese_display_label": _text(props.get(decision_intelligence.TECH_PROP_JAPANESE_DISPLAY_LABEL)),
        "plain_summary": _text(props.get(TECH_PROP_PLAIN_SUMMARY)),
        "topic_trigger": _text(props.get(TECH_PROP_TOPIC_TRIGGER)),
        "category": _select(props.get(decision_intelligence.TECH_PROP_CATEGORY)),
        "short_rationale": _text(props.get(decision_intelligence.TECH_PROP_SHORT_RATIONALE)),
        "screening_reason": _text(props.get(decision_intelligence.TECH_PROP_SCREENING_REASON)),
        "canonical_entity_id": _text(props.get(decision_intelligence.TECH_PROP_ENTITY_ID)),
        "assessment_state": _select(props.get(decision_intelligence.TECH_PROP_ASSESSMENT_STATE)),
        "tracking_status": _select(props.get(decision_intelligence.TECH_PROP_TRACKING_STATUS)),
        "tracking_eligibility": bool(
            (props.get(decision_intelligence.TECH_PROP_TRACKING_ELIGIBILITY) or {}).get("checkbox")
        ),
        "last_reviewed": _date(props.get(decision_intelligence.TECH_PROP_LAST_REVIEWED)),
    }


def _subscriber_context(page: dict) -> dict[str, Any]:
    props = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or ""),
        "entity_id": _text(props.get(decision_intelligence.SUB_PROP_ENTITY_ID)),
        "plain_summary": _text(props.get(SUB_PROP_PLAIN_SUMMARY)),
        "topic_trigger": _text(props.get(SUB_PROP_TOPIC_TRIGGER)),
        "member_score_change": _number(props.get(SUB_PROP_MEMBER_SCORE_CHANGE)),
        "member_change_at": _date(props.get(SUB_PROP_MEMBER_CHANGE_AT)),
        "member_change_reason": _text(props.get(SUB_PROP_MEMBER_CHANGE_REASON)),
    }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _member_change_highlights(events: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """Select one durable member-facing score movement per entity.

    Decision History is authoritative. Only CHANGE events whose score moved by at
    least the product meaningful threshold qualify. During the current product
    month, the largest absolute movement wins (latest wins ties), so +25 followed
    by +6 or 0 cannot hide the +25 from the monthly member view. If an entity has no
    qualifying movement this month, its latest historical meaningful movement is
    retained for durable detail-page context.
    """
    tz = ZoneInfo(decision_intelligence.PRODUCT_TIMEZONE)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if str(event.get("snapshot_type") or "").upper() != "CHANGE":
            continue
        delta = event.get("score_delta")
        if not isinstance(delta, (int, float)) or isinstance(delta, bool):
            continue
        if abs(float(delta)) < decision_intelligence.MEANINGFUL_SCORE_DELTA:
            continue
        entity_id = str(event.get("canonical_entity_id") or "").strip()
        reviewed = _parse_datetime(event.get("reviewed_at"))
        if not entity_id or reviewed is None:
            continue
        normalized = dict(event)
        normalized["_reviewed_dt"] = reviewed
        grouped.setdefault(entity_id, []).append(normalized)

    selected: dict[str, dict[str, Any]] = {}
    for entity_id, candidates in grouped.items():
        this_month = []
        for event in candidates:
            local = event["_reviewed_dt"].astimezone(tz)
            if (local.year, local.month) == (now_local.year, now_local.month):
                this_month.append(event)
        if this_month:
            winner = max(
                this_month,
                key=lambda e: (abs(float(e.get("score_delta") or 0)), e["_reviewed_dt"]),
            )
        else:
            winner = max(candidates, key=lambda e: e["_reviewed_dt"])
        winner = dict(winner)
        winner.pop("_reviewed_dt", None)
        selected[entity_id] = winner
    return selected


def _same_instant(left: str | None, right: str | None) -> bool:
    a, b = _parse_datetime(left), _parse_datetime(right)
    if a is None or b is None:
        return bool(left and right and left == right)
    return a.astimezone(timezone.utc) == b.astimezone(timezone.utc)


def _member_change_reason(event: dict[str, Any], desired: dict[str, Any] | None) -> str:
    """Use natural current-review context when safe; otherwise preserve factual History wording."""
    desired = desired or {}
    if _same_instant(event.get("reviewed_at"), desired.get("last_reviewed")):
        topic = str(desired.get("topic_trigger") or "").strip()
        if topic:
            return topic
    reason = str(event.get("change_reason") or "").strip()
    if reason and reason != "No meaningful decision change":
        return reason
    return ""


def _schema_properties(data_source_id: str, database_id: str, label: str) -> dict:
    try:
        res = requests.get(
            decision_intelligence._schema_url(data_source_id, database_id),
            headers=decision_intelligence._headers(),
            timeout=15,
        )
        res.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Run132 {label} schema preflight failed: {exc}") from exc
    return res.json().get("properties", {})


def _require_context_columns(properties: dict, label: str) -> None:
    missing = []
    wrong = []
    for name in (TECH_PROP_PLAIN_SUMMARY, TECH_PROP_TOPIC_TRIGGER):
        prop = properties.get(name)
        if not prop:
            missing.append(name)
            continue
        prop_type = prop.get("type")
        if prop_type != "rich_text":
            wrong.append(f"{name}:{prop_type}")
    if missing or wrong:
        parts = []
        if missing:
            parts.append("missing=" + ", ".join(missing))
        if wrong:
            parts.append("type=" + ", ".join(wrong))
        raise ValueError(f"Run132 {label} schema incompatible: " + " / ".join(parts))


def _require_member_change_columns(properties: dict, label: str) -> None:
    expected = {
        SUB_PROP_MEMBER_SCORE_CHANGE: "number",
        SUB_PROP_MEMBER_CHANGE_AT: "date",
        SUB_PROP_MEMBER_CHANGE_REASON: "rich_text",
    }
    missing = [name for name in expected if name not in properties]
    wrong = [
        f"{name}:{(properties.get(name) or {}).get('type')}"
        for name, expected_type in expected.items()
        if name in properties and (properties.get(name) or {}).get("type") != expected_type
    ]
    if missing or wrong:
        parts = []
        if missing:
            parts.append("missing=" + ", ".join(missing))
        if wrong:
            parts.append("type=" + ", ".join(wrong))
        raise ValueError(f"Run132 {label} member-change schema incompatible: " + " / ".join(parts))


def preflight_context_first_schema() -> None:
    """Fail before Product Review if reader-facing context/change fields cannot be persisted."""
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        return
    tech = _schema_properties(
        decision_intelligence.NOTION_TECH_DATA_SOURCE_ID,
        decision_intelligence.NOTION_TECH_DATABASE_ID,
        "Technology Intelligence DB",
    )
    _require_context_columns(tech, "Technology Intelligence DB")

    if decision_intelligence.ENABLE_SUBSCRIBER_TECH_SYNC:
        sub = _schema_properties(
            decision_intelligence.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID,
            decision_intelligence.NOTION_SUBSCRIBER_TECH_DATABASE_ID,
            "Subscriber Technology DB",
        )
        _require_context_columns(sub, "Subscriber Technology DB")
        _require_member_change_columns(sub, "Subscriber Technology DB")


def _patch_context(page_id: str, properties: dict[str, dict], label: str) -> None:
    if not page_id or not properties:
        return
    res = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": properties},
        headers=decision_intelligence._headers(),
        timeout=20,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Run132 {label} patch failed: HTTP {res.status_code} {res.text[:500]}")


def enrich_context_first(previous_reviewed: dict[str, str | None] | None = None) -> dict[str, Any]:
    """Backfill/refresh reader context and durable change memory for member inventory.

    `previous_reviewed` is the snapshot captured immediately before Product Review.
    When it is unavailable, existing Topic Trigger copy is preserved rather than
    assuming every record was just reviewed. Existing member Plain Summary is never
    overwritten, and empty internal/history values are never propagated to members.

    Durable member change fields are rebuilt from append-only Decision History, not
    from the mutable current `Score Change`, so later no-change reviews cannot erase
    a change members still need to understand.
    """
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        return {"enabled": False, "reason": "decision_intelligence_disabled"}

    has_review_snapshot = previous_reviewed is not None
    previous_reviewed = dict(previous_reviewed or {})
    pages = decision_intelligence.query_technology_records(max_records=5000)
    desired_by_id: dict[str, dict[str, Any]] = {}
    internal_updated = 0
    internal_preserved = 0

    for page in pages:
        state = _page_state(page)
        entity_id = state["canonical_entity_id"]
        if not entity_id or state["assessment_state"] != "ASSESSED":
            continue

        eligible = bool(state["tracking_eligibility"]) and state["tracking_status"] != "ARCHIVED"
        if not eligible:
            continue

        reviewed_now = has_review_snapshot and (
            entity_id not in previous_reviewed
            or previous_reviewed.get(entity_id) != state.get("last_reviewed")
        )
        plain = derive_plain_summary(state)
        if state.get("topic_trigger") and not reviewed_now:
            topic = str(state["topic_trigger"]).strip()
        else:
            topic = derive_topic_trigger(state)

        patch: dict[str, dict] = {}
        if plain and not state.get("plain_summary"):
            patch[TECH_PROP_PLAIN_SUMMARY] = _rt(plain)
        if topic and (
            not state.get("topic_trigger")
            or (reviewed_now and topic != state.get("topic_trigger"))
        ):
            patch[TECH_PROP_TOPIC_TRIGGER] = _rt(topic)
        if patch:
            _patch_context(state["page_id"], patch, "Technology Intelligence")
            internal_updated += 1
        else:
            internal_preserved += 1

        desired_by_id[entity_id] = {
            "plain_summary": plain,
            "topic_trigger": topic,
            "reviewed_now": reviewed_now,
            "last_reviewed": state.get("last_reviewed"),
        }

    member_highlights: dict[str, dict[str, Any]] = {}
    history_configured = bool(
        decision_intelligence.NOTION_HISTORY_DATA_SOURCE_ID
        or decision_intelligence.NOTION_HISTORY_DATABASE_ID
    )
    if decision_intelligence.ENABLE_SUBSCRIBER_TECH_SYNC and history_configured:
        history_pages = decision_intelligence.query_history_records(max_records=10000)
        history_events = [decision_intelligence.history_page_to_state(page) for page in history_pages]
        member_highlights = _member_change_highlights(history_events)

    subscriber_sync = {"enabled": False}
    subscriber_updated = 0
    subscriber_preserved = 0
    subscriber_missing = 0
    member_change_updated = 0
    member_change_preserved = 0

    if decision_intelligence.ENABLE_SUBSCRIBER_TECH_SYNC:
        subscriber_sync = decision_intelligence.sync_subscriber_technology_db()
        destination = decision_intelligence._query_external_db(
            decision_intelligence.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID,
            decision_intelligence.NOTION_SUBSCRIBER_TECH_DATABASE_ID,
            max_records=5000,
        )
        dest_by_id: dict[str, dict] = {}
        for page in destination:
            ctx = _subscriber_context(page)
            entity_id = ctx.get("entity_id") or ""
            if entity_id and entity_id not in dest_by_id:
                dest_by_id[entity_id] = ctx

        for entity_id, desired in desired_by_id.items():
            current = dest_by_id.get(entity_id)
            if not current:
                subscriber_missing += 1
                continue
            patch: dict[str, dict] = {}
            if desired["plain_summary"] and not current.get("plain_summary"):
                patch[SUB_PROP_PLAIN_SUMMARY] = _rt(desired["plain_summary"])
            if desired["topic_trigger"] and (
                not current.get("topic_trigger")
                or (
                    desired["reviewed_now"]
                    and desired["topic_trigger"] != current.get("topic_trigger")
                )
            ):
                patch[SUB_PROP_TOPIC_TRIGGER] = _rt(desired["topic_trigger"])

            highlight = member_highlights.get(entity_id)
            if highlight:
                change_score = highlight.get("score_delta")
                change_at = str(highlight.get("reviewed_at") or "").strip()
                same_change = (
                    current.get("member_score_change") == change_score
                    and _same_instant(current.get("member_change_at"), change_at)
                )
                if not same_change:
                    patch[SUB_PROP_MEMBER_SCORE_CHANGE] = _number_prop(change_score)
                    patch[SUB_PROP_MEMBER_CHANGE_AT] = _date_prop(change_at)
                    reason = _member_change_reason(highlight, desired)
                    if reason:
                        patch[SUB_PROP_MEMBER_CHANGE_REASON] = _rt(reason)
                    member_change_updated += 1
                elif not current.get("member_change_reason"):
                    reason = _member_change_reason(highlight, desired)
                    if reason:
                        patch[SUB_PROP_MEMBER_CHANGE_REASON] = _rt(reason)
                        member_change_updated += 1
                    else:
                        member_change_preserved += 1
                else:
                    # Keep the original explanation for the selected event. In particular,
                    # do not replace a natural reason with mechanical History wording on a
                    # later no-change run.
                    member_change_preserved += 1
            elif current.get("member_score_change") is not None:
                # History is authoritative but absence of a qualifying event is not permission
                # to erase existing member copy. Preserve rather than guessing/clearing.
                member_change_preserved += 1

            if patch:
                _patch_context(current["page_id"], patch, "Subscriber Technology")
                subscriber_updated += 1
            else:
                subscriber_preserved += 1

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "eligible_records": len(desired_by_id),
        "internal_updated": internal_updated,
        "internal_preserved": internal_preserved,
        "subscriber_updated": subscriber_updated,
        "subscriber_preserved": subscriber_preserved,
        "subscriber_missing": subscriber_missing,
        "member_change_candidates": len(member_highlights),
        "member_change_updated": member_change_updated,
        "member_change_preserved": member_change_preserved,
        "subscriber_sync": subscriber_sync,
    }