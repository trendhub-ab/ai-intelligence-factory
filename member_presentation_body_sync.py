#!/usr/bin/env python3
"""Render readable, deterministic member-page bodies for the clean presentation DB.

Run166 keeps the presentation database useful on both desktop and mobile by
turning already-sanitized properties into a visible decision brief. No model or
Gemini request is made. The body is stored inside one AUTO callout so future
syncs can replace only the generated section while preserving manual notes.

Notion API note:
A parent callout and its nested children are created in two API operations.
Appending a callout carrying nested ``children`` in the same request is rejected
by the 2026-03-11 API. Keeping those writes separate also makes interrupted runs
recoverable on the next sync.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any

import requests

import decision_intelligence
import member_presentation_sync

AUTO_PREFIX = "🧭 判断サマリー｜AUTO"
REQUEST_SLEEP_SECONDS = max(0.0, float(os.environ.get("MEMBER_BODY_REQUEST_SLEEP", "0.34")))

STATUS_LABEL = {
    "ADOPT": "本格導入を検討してよい",
    "TEST": "まず小さく試す",
    "WATCH": "今は待って追跡する",
    "AVOID": "現時点では見送る",
}
STATUS_COLOR = {
    "ADOPT": "green_background",
    "TEST": "blue_background",
    "WATCH": "yellow_background",
    "AVOID": "red_background",
}
_URL_RE = re.compile(r"https?://[^\s\]\[()<>、,。]+")


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", _norm(value)).casefold()


def _signature(state: dict[str, Any]) -> str:
    keys = (
        "sync_id",
        "name",
        "plain_summary",
        "status",
        "score",
        "judgment_reason",
        "topic",
        "next_action",
        "main_risk",
        "best_for",
        "avoid_for",
        "confidence",
        "readiness",
        "category",
        "classification",
        "change_reason",
        "important_at",
        "last_reviewed",
        "evidence",
        "primary_url",
        "related_article",
    )
    payload = {key: state.get(key) for key in keys}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _auto_label(state: dict[str, Any]) -> str:
    return f"{AUTO_PREFIX}｜{_signature(state)}"


def _rich_text(text: str, *, bold: bool = False, url: str | None = None) -> list[dict[str, Any]]:
    text = _norm(text)[:1900]
    if not text:
        return []
    item: dict[str, Any] = {
        "type": "text",
        "text": {"content": text},
        "annotations": {"bold": bool(bold)},
    }
    if url:
        item["text"]["link"] = {"url": url}
    return [item]


def _paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _heading(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": _rich_text(text, bold=True)},
    }


def _link_paragraph(label: str, url: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(label, url=url)},
    }


def _status_summary(state: dict[str, Any]) -> str:
    status = _norm(state.get("status")) or "—"
    score = state.get("score")
    score_text = f"{int(score)}/100" if isinstance(score, (int, float)) else "—"
    readiness = _norm(state.get("readiness")) or "—"
    confidence = _norm(state.get("confidence")) or "—"
    return f"{status} {score_text}｜実用度 {readiness}｜根拠 {confidence}"


def _decision_basis_reason(state: dict[str, Any]) -> str:
    """Explain the decision from existing evaluation fields when source copy duplicates topic."""
    status = _norm(state.get("status"))
    score = state.get("score")
    readiness = _norm(state.get("readiness")) or "—"
    confidence = _norm(state.get("confidence")) or "—"
    metrics: list[str] = []
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        metrics.append(f"判断スコア{int(score)}点")
    metrics.append(f"実用度{readiness}")
    metrics.append(f"根拠の確かさ{confidence}")
    basis = "、".join(metrics)
    conclusion = {
        "ADOPT": "現時点では導入候補として扱う判断です。",
        "TEST": "現時点では小さく検証してから本番判断へ進む位置づけです。",
        "WATCH": "現時点では導入を急がず、変化を追跡する位置づけです。",
        "AVOID": "現時点では新規採用を見送る位置づけです。",
    }.get(status, "現在の条件を確認しながら判断する位置づけです。")
    return f"{basis}を踏まえ、{conclusion}"


def _extract_urls(*values: str) -> list[str]:
    urls: list[str] = []
    for raw in values:
        for url in _URL_RE.findall(_norm(raw)):
            if url not in urls:
                urls.append(url)
    return urls


def _build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    status = _norm(state.get("status"))
    conclusion = STATUS_LABEL.get(status, "現在の条件を確認して判断する")

    children.append(_paragraph(_status_summary(state)))
    children.append(_heading("結論"))
    children.append(_paragraph(f"{status or '—'} — {conclusion}。"))

    action = _norm(state.get("next_action"))
    if action:
        children.append(_heading("次にやること"))
        children.append(_paragraph(action))

    summary = _norm(state.get("plain_summary"))
    if summary:
        children.append(_heading("これは何？"))
        children.append(_paragraph(summary))

    topic = _norm(state.get("topic"))
    if topic:
        children.append(_heading("なぜ今見る？"))
        children.append(_paragraph(topic))

    reason = _norm(state.get("judgment_reason"))
    if reason and topic and _norm_key(reason) == _norm_key(topic):
        reason = _decision_basis_reason(state)
    if reason:
        children.append(_heading("判断理由"))
        children.append(_paragraph(reason))

    risk = _norm(state.get("main_risk"))
    if risk:
        children.append(_heading("主なリスク"))
        children.append(_paragraph(risk))

    best_for = _norm(state.get("best_for"))
    if best_for:
        children.append(_heading("向いている用途"))
        children.append(_paragraph(best_for))

    avoid_for = _norm(state.get("avoid_for"))
    if avoid_for:
        children.append(_heading("向いていない用途"))
        children.append(_paragraph(avoid_for))

    change_reason = _norm(state.get("change_reason"))
    if change_reason:
        children.append(_heading("評価が変わった理由"))
        children.append(_paragraph(change_reason))

    evidence = _norm(state.get("evidence"))
    primary_url = _norm(state.get("primary_url"))
    related_article = _norm(state.get("related_article"))
    urls = _extract_urls(evidence, primary_url)
    if urls or related_article:
        children.append(_heading("確認する一次情報"))
        for index, url in enumerate(urls[:5], 1):
            children.append(_link_paragraph(f"一次情報 {index}", url))
        if related_article:
            children.append(_link_paragraph("関連記事", related_article))

    return children


def _callout_data(state: dict[str, Any]) -> dict[str, Any]:
    status = _norm(state.get("status"))
    return {
        "rich_text": _rich_text(_auto_label(state), bold=True),
        "icon": {"type": "emoji", "emoji": "🧭"},
        "color": STATUS_COLOR.get(status, "gray_background"),
    }


def _new_callout_block(state: dict[str, Any]) -> dict[str, Any]:
    """Return only the parent block; children must be appended separately."""
    return {
        "object": "block",
        "type": "callout",
        "callout": _callout_data(state),
    }


def _plain_rich_text(values: list[dict[str, Any]] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    ).strip()


def _block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type") or "")
    payload = block.get(block_type) or {}
    return _plain_rich_text(payload.get("rich_text"))


def _body_fingerprint(blocks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(str(block.get("type") or ""), _block_text(block)) for block in blocks]


def _body_matches(actual: list[dict[str, Any]], state: dict[str, Any]) -> bool:
    return _body_fingerprint(actual) == _body_fingerprint(_build_children(state))


def _request(method: str, url: str, *, json_payload: dict[str, Any] | None = None) -> requests.Response:
    response: requests.Response | None = None
    for attempt in range(5):
        response = requests.request(
            method,
            url,
            json=json_payload,
            headers=decision_intelligence._headers(),
            timeout=30,
        )
        if response.status_code == 429:
            time.sleep(max(0.8, float(response.headers.get("Retry-After") or 1.0)))
            continue
        if 500 <= response.status_code < 600 and attempt < 4:
            time.sleep(1.0 + attempt)
            continue
        return response
    assert response is not None
    return response


def _children(block_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        res = _request("GET", url)
        if res.status_code != 200:
            raise RuntimeError(f"Member body child fetch failed {block_id}: {res.status_code} {res.text[:500]}")
        payload = res.json()
        results.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            return results
        cursor = str(payload.get("next_cursor") or "") or None


def _delete_block(block_id: str) -> None:
    res = _request("DELETE", f"https://api.notion.com/v1/blocks/{block_id}")
    if res.status_code not in {200, 204}:
        raise RuntimeError(f"Member body block delete failed {block_id}: {res.status_code} {res.text[:500]}")


def _append_children(block_id: str, children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not children:
        return []
    res = _request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{block_id}/children",
        json_payload={"children": children},
    )
    if res.status_code != 200:
        raise RuntimeError(f"Member body append failed {block_id}: {res.status_code} {res.text[:500]}")
    return list((res.json() or {}).get("results") or [])


def _create_auto_callout(page_id: str, state: dict[str, Any]) -> None:
    created = _append_children(page_id, [_new_callout_block(state)])
    if not created:
        raise RuntimeError(f"Member AUTO callout creation returned no block: {page_id}")
    callout_id = str((created[0] or {}).get("id") or "")
    if not callout_id:
        raise RuntimeError(f"Member AUTO callout creation returned no id: {page_id}")
    _append_children(callout_id, _build_children(state))


def _replace_auto_callout(block: dict[str, Any], state: dict[str, Any]) -> None:
    block_id = str(block.get("id") or "")
    if not block_id:
        raise RuntimeError("Member AUTO callout is missing block id")
    for child in _children(block_id):
        child_id = str(child.get("id") or "")
        if child_id:
            _delete_block(child_id)
    res = _request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{block_id}",
        json_payload={"callout": _callout_data(state)},
    )
    if res.status_code != 200:
        raise RuntimeError(f"Member AUTO callout update failed {block_id}: {res.status_code} {res.text[:500]}")
    _append_children(block_id, _build_children(state))


def sync_member_page_bodies() -> dict[str, Any]:
    if not decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    data_source_id = member_presentation_sync.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID
    database_id = member_presentation_sync.NOTION_MEMBER_PRESENTATION_DATABASE_ID
    if not (data_source_id or database_id):
        raise ValueError("Member presentation DB is not configured")

    pages = decision_intelligence._query_external_db(data_source_id, database_id, max_records=5000)
    created = updated = unchanged = duplicates_removed = manual_pages = 0

    for page in pages:
        state = member_presentation_sync._destination_state(page)
        page_id = str(state.get("page_id") or page.get("id") or "").strip()
        if not page_id or not state.get("sync_id"):
            continue
        root_blocks = _children(page_id)
        auto_blocks = [
            block
            for block in root_blocks
            if block.get("type") == "callout" and _block_text(block).startswith(AUTO_PREFIX)
        ]
        expected_label = _auto_label(state)
        first_auto = auto_blocks[0] if auto_blocks else None
        first_auto_children = _children(str(first_auto.get("id"))) if first_auto and first_auto.get("id") else []
        if (
            first_auto
            and _block_text(first_auto) == expected_label
            and _body_matches(first_auto_children, state)
        ):
            unchanged += 1
            for duplicate in auto_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "")
                if duplicate_id:
                    _delete_block(duplicate_id)
                    duplicates_removed += 1
            continue

        if first_auto:
            _replace_auto_callout(first_auto, state)
            updated += 1
            for duplicate in auto_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "")
                if duplicate_id:
                    _delete_block(duplicate_id)
                    duplicates_removed += 1
        else:
            if root_blocks:
                manual_pages += 1
            _create_auto_callout(page_id, state)
            created += 1
        if REQUEST_SLEEP_SECONDS:
            time.sleep(REQUEST_SLEEP_SECONDS)

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "total": len(pages),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "duplicates_removed": duplicates_removed,
        "manual_pages_preserved": manual_pages,
    }


def main() -> None:
    print(sync_member_page_bodies())


if __name__ == "__main__":
    main()
