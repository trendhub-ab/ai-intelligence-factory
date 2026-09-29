#!/usr/bin/env python3
"""Deterministically refresh the paid-member monthly Decision Brief.

This is a presentation-only sidecar. It consumes the already-reviewed member
presentation DB and never calls Gemini or any other model. The same stable page
URL is retained while the page body and month label are refreshed after each
successful member presentation sync.

Safety:
- ZERO model calls.
- Read only from the canonical member presentation DB.
- Content-first replacement: append the complete new body before deleting the
  previously visible body, so a mid-flight failure does not leave an empty page.
- Never changes Technology/Content/History source records.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

import decision_intelligence
import member_presentation_sync as member

PAGE_ID = os.environ.get("MEMBER_MONTHLY_BRIEF_PAGE_ID", "").strip()
TOP_LIMIT = max(1, min(10, int(os.environ.get("MEMBER_MONTHLY_BRIEF_TOP_LIMIT", "5"))))
CHANGE_LIMIT = max(1, min(10, int(os.environ.get("MEMBER_MONTHLY_BRIEF_CHANGE_LIMIT", "5"))))
PRODUCT_TIMEZONE = os.environ.get("DI_PRODUCT_TIMEZONE", "Asia/Tokyo")
REQUEST_PACING_SECONDS = max(0.0, float(os.environ.get("MEMBER_MONTHLY_BRIEF_PACING_SECONDS", "0.25")))


def _headers() -> dict[str, str]:
    return decision_intelligence._headers()


def _request(method: str, url: str, *, payload: dict | None = None) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(5):
        last = requests.request(method, url, headers=_headers(), json=payload, timeout=30)
        if last.status_code == 429:
            retry = float(last.headers.get("Retry-After") or 1.0)
            time.sleep(max(0.5, min(retry, 8.0)))
            continue
        if 500 <= last.status_code < 600 and attempt < 4:
            time.sleep(0.8 + attempt)
            continue
        if REQUEST_PACING_SECONDS:
            time.sleep(REQUEST_PACING_SECONDS)
        return last
    assert last is not None
    return last


def _rt(text: str, *, bold: bool = False, link: str = "") -> dict[str, Any]:
    value = " ".join(str(text or "").split()).strip()[:1900]
    row: dict[str, Any] = {
        "type": "text",
        "text": {"content": value},
        "annotations": {"bold": bold},
    }
    if link:
        row["text"]["link"] = {"url": link}
    return row


def _paragraph(*parts: dict[str, Any]) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": list(parts)}}


def _heading(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_rt(text)]}}


def _bullet(text: str) -> dict[str, Any]:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_rt(text)]}}


def _callout(text: str, emoji: str = "📌") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": emoji},
            "rich_text": [_rt(text)],
        },
    }


def _divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _page_url(page_id: str) -> str:
    compact = str(page_id or "").replace("-", "")
    return f"https://app.notion.com/p/{compact}" if compact else ""


def _query_states() -> list[dict[str, Any]]:
    if not (
        member.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID
        or member.NOTION_MEMBER_PRESENTATION_DATABASE_ID
    ):
        raise ValueError("member presentation DB is not configured")
    pages = decision_intelligence._query_external_db(
        member.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
        member.NOTION_MEMBER_PRESENTATION_DATABASE_ID,
        max_records=5000,
    )
    states = [member._destination_state(page) for page in pages]
    return [
        state for state in states
        if state.get("page_id")
        and state.get("sync_id")
        and state.get("name")
        and state.get("status") in {"ADOPT", "TEST", "WATCH", "AVOID"}
    ]


def _score(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else -1.0


def select_top(states: list[dict[str, Any]], *, limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    practical = [
        s for s in states
        if s.get("classification") == "実務判断"
        and s.get("status") in {"ADOPT", "TEST"}
        and s.get("confidence") != "低"
        and _score(s.get("score")) >= 0
    ]
    ranked = [s for s in practical if isinstance(s.get("rank"), (int, float))]
    ranked.sort(key=lambda s: (float(s.get("rank") or 9999), -_score(s.get("score")), str(s.get("name") or "")))
    selected = ranked[:limit]
    selected_ids = {s["sync_id"] for s in selected}
    remainder = [s for s in practical if s.get("sync_id") not in selected_ids]
    remainder.sort(
        key=lambda s: (
            -_score(s.get("score")),
            0 if s.get("confidence") == "高" else 1,
            0 if s.get("readiness") == "高" else 1,
            str(s.get("name") or ""),
        )
    )
    return (selected + remainder)[:limit]


def select_changes(states: list[dict[str, Any]], *, limit: int = CHANGE_LIMIT) -> list[dict[str, Any]]:
    changed = [
        s for s in states
        if s.get("current_month_change")
        and isinstance(s.get("delta"), (int, float))
        and abs(float(s.get("delta") or 0)) >= decision_intelligence.MEANINGFUL_SCORE_DELTA
    ]
    changed.sort(
        key=lambda s: (
            -abs(float(s.get("delta") or 0)),
            -_score(s.get("score")),
            str(s.get("name") or ""),
        )
    )
    return changed[:limit]


def build_blocks(states: list[dict[str, Any]], *, now: datetime | None = None) -> tuple[str, list[dict[str, Any]], int, int]:
    tz = ZoneInfo(PRODUCT_TIMEZONE)
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    title = f"会員限定Decision Brief｜{local_now.year}年{local_now.month}月"
    top = select_top(states)
    changes = select_changes(states)

    blocks: list[dict[str, Any]] = [
        _callout(
            f"{local_now.month}月の最新判断です。ニュースを並べるのではなく、"
            "今見るべきAI・技術と、使う・試す・待つ・避ける判断を短時間で確認できます。"
        ),
        _heading(2, "今月の結論"),
    ]
    if top:
        for state in top:
            score = int(round(_score(state.get("score"))))
            action = str(state.get("next_action") or "").strip()
            blocks.append(_bullet(f"{state['name']} — {state['status']}｜{score}点 — {action}"))
    else:
        blocks.append(_paragraph(_rt("現在、会員向けに提示できる評価済み候補がありません。")))

    for idx, state in enumerate(top, 1):
        score = int(round(_score(state.get("score"))))
        blocks.extend([
            _heading(2, f"{idx}｜{state['name']} — {state['status']}｜{score}点"),
            _paragraph(_rt("使える場面：", bold=True), _rt(state.get("best_for") or state.get("plain_summary") or "用途を確認中です。")),
            _paragraph(_rt("判断のポイント：", bold=True), _rt(state.get("judgment_reason") or "現在の一次情報を基に判断しています。")),
            _paragraph(_rt("使う前に確認すること：", bold=True), _rt(state.get("main_risk") or "自社条件との適合を確認してください。")),
            _paragraph(_rt("次の一手：", bold=True), _rt(state.get("next_action") or "小さく検証してから次の判断へ進みます。")),
            _paragraph(
                _rt("DBで詳しく見る", bold=True, link=_page_url(state.get("page_id") or "")),
                _rt(" ｜ "),
                _rt("公式", link=state.get("primary_url") or ""),
            ),
        ])

    blocks.extend([_divider(), _heading(2, "今月、判断を変える必要があるもの")])
    if not changes:
        blocks.append(_paragraph(_rt("現時点では、判断を変えるほどの重要変化はありません。変化がないことも判断材料です。")))
    for state in changes:
        delta = float(state.get("delta") or 0)
        sign = "+" if delta > 0 else ""
        blocks.extend([
            _heading(3, f"{state['name']} — 評価 {sign}{int(delta) if delta.is_integer() else delta:g}"),
            _paragraph(_rt(state.get("change_reason") or state.get("topic") or "重要な変化を検知しました。")),
            _paragraph(_rt("次の一手：", bold=True), _rt(state.get("next_action") or "現在の判断条件を再確認します。")),
            _paragraph(_rt("DBで確認", link=_page_url(state.get("page_id") or ""))),
        ])

    blocks.extend([
        _divider(),
        _callout(
            f"最終自動更新：{local_now.date().isoformat()} JST。"
            "根拠・実用度・リスク・次のActionはAI意思決定DBで確認できます。",
            emoji="🧭",
        ),
    ])
    return title, blocks, len(top), len(changes)


def _children(page_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = ""
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        res = _request("GET", url)
        if res.status_code != 200:
            raise RuntimeError(f"monthly brief child query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json()
        rows.extend(body.get("results") or [])
        if not body.get("has_more"):
            return rows
        cursor = str(body.get("next_cursor") or "")
        if not cursor:
            raise RuntimeError("monthly brief pagination inconsistent")


def _append(page_id: str, blocks: list[dict[str, Any]]) -> None:
    res = _request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        payload={"children": blocks},
    )
    if res.status_code != 200:
        raise RuntimeError(f"monthly brief append failed: HTTP {res.status_code} {res.text[:500]}")


def _delete(block_id: str) -> None:
    res = _request("DELETE", f"https://api.notion.com/v1/blocks/{block_id}")
    if res.status_code != 200:
        raise RuntimeError(f"monthly brief old-block cleanup failed: HTTP {res.status_code} {res.text[:500]}")


def _rename(page_id: str, title: str) -> None:
    res = _request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{page_id}",
        payload={"properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}}},
    )
    if res.status_code != 200:
        raise RuntimeError(f"monthly brief title update failed: HTTP {res.status_code} {res.text[:500]}")


def sync_monthly_brief(*, now: datetime | None = None) -> dict[str, Any]:
    if not decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    if not PAGE_ID:
        raise ValueError("MEMBER_MONTHLY_BRIEF_PAGE_ID is required")

    states = _query_states()
    title, blocks, top_count, change_count = build_blocks(states, now=now)
    old = _children(PAGE_ID)

    # Content-first replacement. The old member surface stays visible until the
    # complete replacement body has been accepted by Notion.
    _append(PAGE_ID, blocks)
    for block in old:
        block_id = str(block.get("id") or "").strip()
        if block_id:
            _delete(block_id)
    _rename(PAGE_ID, title)

    return {
        "enabled": True,
        "zero_model_calls": True,
        "source_records": len(states),
        "top_count": top_count,
        "important_change_count": change_count,
        "old_blocks_deleted": sum(1 for b in old if b.get("id")),
        "page_id": PAGE_ID,
        "title": title,
    }


def main() -> None:
    print(json.dumps(sync_monthly_brief(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
