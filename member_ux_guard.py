#!/usr/bin/env python3
"""Run169: customer-facing guard for the member Decision Intelligence UI.

This layer fixes presentation-only defects without changing Product Review scores,
Evidence, article generation, or the internal decision model.

Goals:
- never publish a member record with an empty ``これは何？``;
- recover reviewed plain summaries from ``external_reviews/*.json`` first;
- keep the homepage shortlist to exactly the three highest-value practical picks;
- render a clean ``🧭 判断サマリー`` label without AUTO/hash internals;
- recognize legacy generated callouts safely while preserving manual notes.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import member_presentation_body_sync as body
import member_presentation_sync as mps

VISIBLE_CALLOUT_LABEL = "🧭 判断サマリー"
LEGACY_AUTO_PREFIX = body.AUTO_PREFIX
HOME_SHORTLIST_SIZE = 3

_GENERIC_TOPIC_RE = re.compile(r"^.+の現在の機能・保守状況を確認しています[。.]?$")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_url(value: Any) -> str:
    value = _clean(value)
    if not value:
        return ""
    return value.rstrip("/").casefold()


def _norm_name(value: Any) -> str:
    return _clean(value).casefold()


def load_review_summary_index(root: str | Path = "external_reviews") -> dict[str, dict[str, str]]:
    """Index already-reviewed, evidence-grounded summaries committed to the repo."""
    by_url: dict[str, str] = {}
    by_name: dict[str, str] = {}
    root_path = Path(root)
    if not root_path.exists():
        return {"by_url": by_url, "by_name": by_name}

    for path in sorted(root_path.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("reviews") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ctx = row.get("decision_context") or {}
            if not isinstance(ctx, dict):
                ctx = {}
            summary = _clean(ctx.get("plain_summary") or row.get("description"))
            if not summary:
                continue
            name_key = _norm_name(row.get("name"))
            if name_key:
                by_name[name_key] = summary
            for raw_url in (row.get("primary_url"), row.get("url")):
                url_key = _norm_url(raw_url)
                if url_key:
                    by_url[url_key] = summary
    return {"by_url": by_url, "by_name": by_name}


def review_summary_for_state(state: dict[str, Any], index: dict[str, dict[str, str]]) -> str:
    url_key = _norm_url(state.get("primary_url"))
    if url_key and url_key in index.get("by_url", {}):
        return index["by_url"][url_key]
    name_key = _norm_name(state.get("name"))
    if name_key and name_key in index.get("by_name", {}):
        return index["by_name"][name_key]
    return ""


def _usable(text: Any) -> str:
    text = _clean(text)
    if not text or _GENERIC_TOPIC_RE.match(text):
        return ""
    return text


def fallback_summary(state: dict[str, Any]) -> str:
    """Last-resort non-empty explanation for future records not in review artifacts.

    The external-review summary is preferred. This fallback deliberately avoids
    inventing capabilities; it only rephrases already-stored member-facing fields.
    """
    name = _clean(state.get("name")) or "この項目"
    category = _clean(state.get("category")) or "AI関連"
    classification = _clean(state.get("classification"))
    reason = _usable(state.get("judgment_reason"))
    topic = _usable(state.get("topic"))
    best_for = _usable(state.get("best_for"))

    if classification == "Deep Tech" and reason:
        return f"「{name}」は、{reason.rstrip('。')}という論点を扱う研究・技術です。"
    if best_for:
        return f"「{name}」は、{best_for.rstrip('。')}ときに検討する{category}の技術・サービスです。"
    if topic:
        return f"「{name}」は、{topic.rstrip('。')}という動きを追う{category}の技術・サービスです。"
    if reason:
        return f"「{name}」は、{reason.rstrip('。')}という特徴を持つ{category}の技術・サービスです。"
    return (
        f"「{name}」は、{category}として継続評価している項目です。"
        "詳しい位置づけは下の判断理由と一次情報で確認できます。"
    )


def install_presentation_guard() -> dict[str, int]:
    """Patch the presentation mapper so every outgoing member row has a summary."""
    index = load_review_summary_index()
    original_source_state = mps._source_state
    stats = {"existing": 0, "review_recovered": 0, "fallback": 0, "missing": 0}

    def guarded_source_state(page: dict[str, Any]) -> dict[str, Any] | None:
        state = original_source_state(page)
        if not state:
            return None
        existing = _clean(state.get("plain_summary"))
        if existing:
            stats["existing"] += 1
            state["plain_summary"] = existing
            return state
        recovered = review_summary_for_state(state, index)
        if recovered:
            stats["review_recovered"] += 1
            state["plain_summary"] = recovered
        else:
            stats["fallback"] += 1
            state["plain_summary"] = fallback_summary(state)
        if not _clean(state.get("plain_summary")):
            stats["missing"] += 1
            raise ValueError(f"Member summary guard failed closed: {state.get('sync_id') or state.get('name')}")
        return state

    mps._source_state = guarded_source_state
    # Defense in depth: the workflow also passes 3, but the product contract lives here.
    mps.MEMBER_HOME_MAX = HOME_SHORTLIST_SIZE
    return stats


def run_presentation_sync() -> dict[str, Any]:
    stats = install_presentation_guard()
    result = mps.sync_member_presentation()
    result["summary_guard"] = stats
    result["homepage_contract"] = HOME_SHORTLIST_SIZE
    if stats["missing"]:
        raise RuntimeError(f"Member summary guard left {stats['missing']} missing summaries")
    if result.get("source_records", 0) >= HOME_SHORTLIST_SIZE and result.get("homepage_count") != HOME_SHORTLIST_SIZE:
        raise RuntimeError(
            f"Member homepage contract mismatch: expected {HOME_SHORTLIST_SIZE}, got {result.get('homepage_count')}"
        )
    return result


def _heading_texts(children: list[dict[str, Any]]) -> set[str]:
    return {
        body._block_text(block)
        for block in children
        if block.get("type") == "heading_3"
    }


def _looks_like_generated_visible_callout(block: dict[str, Any], child_cache: dict[str, list[dict[str, Any]]]) -> bool:
    """Recognize our clean generated callout without claiming ordinary manual notes."""
    if block.get("type") != "callout" or body._block_text(block) != VISIBLE_CALLOUT_LABEL:
        return False
    block_id = str(block.get("id") or "")
    if not block_id:
        return False
    children = child_cache.setdefault(block_id, body._children(block_id))
    headings = _heading_texts(children)
    return "結論" in headings and "次にやること" in headings and "判断理由" in headings


def _generated_blocks(
    root_blocks: list[dict[str, Any]], child_cache: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    for block in root_blocks:
        if block.get("type") != "callout":
            continue
        label = body._block_text(block)
        if label.startswith(LEGACY_AUTO_PREFIX):
            generated.append(block)
            continue
        if _looks_like_generated_visible_callout(block, child_cache):
            generated.append(block)
    return generated


def run_body_sync() -> dict[str, Any]:
    """Render member briefs with a customer-safe label while preserving manual notes."""
    if not body.decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    data_source_id = mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID
    database_id = mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID
    if not (data_source_id or database_id):
        raise ValueError("Member presentation DB is not configured")

    # Existing helper functions use _auto_label when creating/updating the callout.
    body._auto_label = lambda _state: VISIBLE_CALLOUT_LABEL

    pages = body.decision_intelligence._query_external_db(data_source_id, database_id, max_records=5000)
    created = updated = unchanged = duplicates_removed = manual_pages = 0

    for page in pages:
        state = mps._destination_state(page)
        page_id = str(state.get("page_id") or page.get("id") or "").strip()
        if not page_id or not state.get("sync_id"):
            continue
        root_blocks = body._children(page_id)
        child_cache: dict[str, list[dict[str, Any]]] = {}
        auto_blocks = _generated_blocks(root_blocks, child_cache)
        first_auto = auto_blocks[0] if auto_blocks else None
        first_id = str((first_auto or {}).get("id") or "")
        first_auto_children = child_cache.get(first_id) if first_id else None
        if first_auto_children is None and first_id:
            first_auto_children = body._children(first_id)

        if (
            first_auto
            and body._block_text(first_auto) == VISIBLE_CALLOUT_LABEL
            and body._body_matches(first_auto_children or [], state)
        ):
            unchanged += 1
            for duplicate in auto_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "")
                if duplicate_id:
                    body._delete_block(duplicate_id)
                    duplicates_removed += 1
            continue

        if first_auto:
            body._replace_auto_callout(first_auto, state)
            updated += 1
            for duplicate in auto_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "")
                if duplicate_id:
                    body._delete_block(duplicate_id)
                    duplicates_removed += 1
        else:
            if root_blocks:
                manual_pages += 1
            body._create_auto_callout(page_id, state)
            created += 1
        if body.REQUEST_SLEEP_SECONDS:
            body.time.sleep(body.REQUEST_SLEEP_SECONDS)

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "total": len(pages),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "duplicates_removed": duplicates_removed,
        "manual_pages_preserved": manual_pages,
        "visible_callout_label": VISIBLE_CALLOUT_LABEL,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python member_ux_guard.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
