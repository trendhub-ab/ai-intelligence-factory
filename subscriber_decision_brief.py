"""Run158 subscriber Decision Brief sidecar.

This module enriches the member-facing AI Decision Intelligence database by adding
one AUTO-managed toggle block to each subscriber page. It never calls Gemini and
never deletes or rewrites manual page content. Existing subscriber properties are
the only factual source used to build the brief.

Run196 centralizes all Notion traffic through a paced retry transport. 429 responses
honor Notion Retry-After guidance, transient 5xx responses back off, and successful
requests are paced individually so a page that needs multiple reads cannot create a
short burst even when the outer page loop is slow enough on average.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests

NOTION_API_KEY = os.environ.get("NOTION_DECISION_INTELLIGENCE_API_KEY", "").strip()
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
SUBSCRIBER_DATABASE_ID = os.environ.get("NOTION_SUBSCRIBER_TECH_DATABASE_ID", "").strip()
SUBSCRIBER_DATA_SOURCE_ID = os.environ.get("NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID", "").strip()
ENABLE_SUBSCRIBER_DECISION_BRIEF = os.environ.get("ENABLE_SUBSCRIBER_DECISION_BRIEF", "true").lower() in {"1", "true", "yes", "on"}
REQUEST_PACING_SECONDS = max(0.0, float(os.environ.get("SUBSCRIBER_DECISION_BRIEF_PACING_SECONDS", "0.40")))
REQUEST_MAX_ATTEMPTS = max(1, int(os.environ.get("SUBSCRIBER_DECISION_BRIEF_REQUEST_MAX_ATTEMPTS", "8")))
RETRY_AFTER_MAX_SECONDS = max(1.0, float(os.environ.get("SUBSCRIBER_DECISION_BRIEF_RETRY_AFTER_MAX_SECONDS", "120")))
SERVER_BACKOFF_MAX_SECONDS = max(1.0, float(os.environ.get("SUBSCRIBER_DECISION_BRIEF_SERVER_BACKOFF_MAX_SECONDS", "12")))

AUTO_MARKER = "🧭 Decision Brief｜AUTO"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _query_url() -> str:
    if SUBSCRIBER_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{SUBSCRIBER_DATA_SOURCE_ID}/query"
    if SUBSCRIBER_DATABASE_ID:
        return f"https://api.notion.com/v1/databases/{SUBSCRIBER_DATABASE_ID}/query"
    raise ValueError("Subscriber Decision Brief requires NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID or NOTION_SUBSCRIBER_TECH_DATABASE_ID")


def _sleep(seconds: float | None = None) -> None:
    delay = REQUEST_PACING_SECONDS if seconds is None else max(0.0, float(seconds))
    if delay:
        time.sleep(delay)


def _response_retry_after(response: requests.Response, attempt: int) -> float:
    """Resolve Notion's rate-limit delay from header/body, with a safe fallback."""
    candidates: list[Any] = []
    try:
        headers = response.headers or {}
        candidates.append(headers.get("Retry-After"))
    except Exception:
        pass
    try:
        body = response.json() or {}
        candidates.append((body.get("additional_data") or {}).get("retry_after"))
    except Exception:
        pass
    for value in candidates:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return min(max(seconds, 0.05), RETRY_AFTER_MAX_SECONDS)
    return min(max(1.0, 2.0 ** min(attempt, 4)), RETRY_AFTER_MAX_SECONDS)


def _request(
    method: str,
    url: str,
    *,
    json_payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> requests.Response:
    """Perform one Notion request with per-request pacing and bounded transient retries."""
    request_fn = getattr(requests, method.lower())
    last: requests.Response | None = None
    for attempt in range(REQUEST_MAX_ATTEMPTS):
        kwargs: dict[str, Any] = {"headers": _headers(), "timeout": timeout}
        if json_payload is not None:
            kwargs["json"] = json_payload
        last = request_fn(url, **kwargs)

        if last.status_code == 429 and attempt < REQUEST_MAX_ATTEMPTS - 1:
            _sleep(_response_retry_after(last, attempt))
            continue
        if 500 <= last.status_code < 600 and attempt < REQUEST_MAX_ATTEMPTS - 1:
            _sleep(min(1.0 * (2 ** attempt), SERVER_BACKOFF_MAX_SECONDS))
            continue

        # Pace every completed request, not merely every page. A normal page often performs
        # two consecutive reads (root children + managed toggle children), which was the
        # Run196 live-rate-limit failure surface.
        _sleep()
        return last

    assert last is not None
    return last


def _plain_text(prop: dict | None) -> str:
    prop = prop or {}
    chunks = prop.get("rich_text") or prop.get("title") or []
    return "".join(str(x.get("plain_text") or (x.get("text") or {}).get("content") or "") for x in chunks).strip()


def _select(prop: dict | None) -> str:
    value = (prop or {}).get("select") or {}
    return str(value.get("name") or "").strip()


def _number(prop: dict | None) -> int | float | None:
    return (prop or {}).get("number")


def _url(prop: dict | None) -> str:
    return str((prop or {}).get("url") or "").strip()


def _date(prop: dict | None) -> str:
    return str(((prop or {}).get("date") or {}).get("start") or "").strip()


def _clip(value: str, limit: int = 1800) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _split_urls(value: str, primary_url: str = "") -> list[str]:
    parts = re.split(r"(?:\r?\n|<br\s*/?>)", value or "", flags=re.I)
    out: list[str] = []
    for item in [primary_url, *parts]:
        item = item.strip()
        if item and item not in out:
            out.append(item)
    return out


def page_to_values(page: dict) -> dict[str, Any]:
    p = page.get("properties") or {}
    return {
        "page_id": page.get("id") or "",
        "name": _plain_text(p.get("技術・プロジェクト名")),
        "display_label": _plain_text(p.get("日本語表示名")),
        "category": _select(p.get("分野（内部）")),
        "adoption_score": _number(p.get("採用スコア（内部）")),
        "adoption_status": _select(p.get("採用判断（内部）")),
        "production_readiness": _select(p.get("実用準備度（内部）")),
        "evidence_confidence": _select(p.get("根拠信頼度（内部）")),
        "plain_summary": _plain_text(p.get("わかりやすい要約（内部）")),
        "topic_trigger": _plain_text(p.get("今回の話題（内部）")),
        "short_rationale": _plain_text(p.get("判断理由（内部）")),
        "best_for": _plain_text(p.get("向いている用途（内部）")),
        "avoid_for": _plain_text(p.get("向いていない用途（内部）")),
        "main_risk": _plain_text(p.get("主リスク（内部）")),
        "primary_url": _url(p.get("公式URL")),
        "evidence_urls": _split_urls(_plain_text(p.get("一次情報URL（内部）")), _url(p.get("公式URL"))),
        "last_reviewed": _date(p.get("最終レビュー日（内部）")),
    }


def _status_conclusion(status: str) -> str:
    return {
        "ADOPT": "結論：ADOPT — 導入を前向きに検討する判断です。",
        "TEST": "結論：TEST — 限定検証してから採否を決める判断です。",
        "WATCH": "結論：WATCH — 今は導入を急がず、継続監視する判断です。",
        "AVOID": "結論：AVOID — 現時点では新規採用を見送る判断です。",
    }.get(str(status or "").upper(), f"結論：{status or '未評価'}")


def _text(content: str, *, bold: bool = False, link: str | None = None) -> dict:
    obj: dict[str, Any] = {"type": "text", "text": {"content": _clip(content, 1900)}}
    if link:
        obj["text"]["link"] = {"url": link}
    if bold:
        obj["annotations"] = {"bold": True}
    return obj


def _paragraph(text: str, *, bold_label: str | None = None) -> dict:
    rich = []
    if bold_label:
        rich.append(_text(bold_label, bold=True))
    if text:
        rich.append(_text(text))
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich}}


def _heading(text: str) -> dict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [_text(text, bold=True)]}}


def _bullet(text: str, link: str | None = None) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_text(text, link=link)]}}


def decision_key(values: dict[str, Any]) -> str:
    score = values.get("adoption_score")
    score_text = f"{int(score)}/100" if isinstance(score, (int, float)) else "—"
    reviewed = str(values.get("last_reviewed") or "")[:10] or "—"
    return (
        f"{str(values.get('adoption_status') or '未評価').upper()} {score_text}"
        f"｜実用度 {values.get('production_readiness') or '—'}"
        f"｜根拠 {values.get('evidence_confidence') or '—'}"
        f"｜最終確認 {reviewed}"
    )


def build_decision_brief_toggle(values: dict[str, Any]) -> dict:
    children: list[dict] = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🧭"},
                "rich_text": [_text(decision_key(values), bold=True)],
            },
        },
        _paragraph(_status_conclusion(str(values.get("adoption_status") or ""))),
    ]

    sections = [
        ("これは何？", values.get("plain_summary")),
        ("なぜ今見るべき？", values.get("topic_trigger")),
        ("判断理由", values.get("short_rationale")),
        ("向いている用途", values.get("best_for")),
        ("向いていない用途", values.get("avoid_for")),
        ("主なリスク", values.get("main_risk")),
    ]
    for title, body in sections:
        body = _clip(str(body or ""))
        if not body:
            continue
        children.extend([_heading(title), _paragraph(body)])

    evidence = values.get("evidence_urls") or []
    if evidence:
        children.append(_heading("一次情報"))
        for url in evidence[:8]:
            children.append(_bullet(url, link=url))

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_text(AUTO_MARKER, bold=True)],
            "children": children,
        },
    }


def _block_text(block: dict) -> str:
    block_type = block.get("type") or ""
    payload = block.get(block_type) or {}
    return "".join(str(x.get("plain_text") or (x.get("text") or {}).get("content") or "") for x in payload.get("rich_text") or []).strip()


def _children_signature(children: list[dict]) -> tuple[tuple[str, str], ...]:
    return tuple((str(child.get("type") or ""), _block_text(child)) for child in children)


def _desired_signature(values: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    toggle = build_decision_brief_toggle(values)
    return _children_signature(toggle["toggle"]["children"])


def _list_children(block_id: str) -> list[dict]:
    rows: list[dict] = []
    cursor = ""
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        res = _request("GET", url, timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Decision Brief children query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json()
        rows.extend(body.get("results") or [])
        if not body.get("has_more"):
            return rows
        cursor = str(body.get("next_cursor") or "")
        if not cursor:
            raise RuntimeError("Decision Brief children pagination inconsistent")


def _managed_toggles(page_id: str) -> list[dict]:
    return [x for x in _list_children(page_id) if x.get("type") == "toggle" and _block_text(x) == AUTO_MARKER]


def _current_signature(toggle_id: str) -> tuple[tuple[str, str], ...]:
    return _children_signature(_list_children(toggle_id))


def _append_toggle(page_id: str, values: dict[str, Any]) -> str:
    res = _request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        json_payload={"children": [build_decision_brief_toggle(values)]},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Decision Brief append failed: HTTP {res.status_code} {res.text[:500]}")
    results = res.json().get("results") or []
    return str((results[0] if results else {}).get("id") or "")


def _delete_block(block_id: str) -> None:
    res = _request("DELETE", f"https://api.notion.com/v1/blocks/{block_id}", timeout=20)
    if res.status_code != 200:
        raise RuntimeError(f"Decision Brief old block cleanup failed: HTTP {res.status_code} {res.text[:500]}")


def sync_page(values: dict[str, Any]) -> str:
    page_id = str(values.get("page_id") or "")
    if not page_id:
        raise ValueError("Subscriber page missing id")
    current = _managed_toggles(page_id)
    if len(current) == 1 and _current_signature(str(current[0].get("id") or "")) == _desired_signature(values):
        return "unchanged"

    # Content-first replacement: append the new managed brief before deleting old AUTO blocks.
    # A mid-flight failure therefore never destroys manual content and usually leaves at least one brief.
    new_id = _append_toggle(page_id, values)
    for block in current:
        old_id = str(block.get("id") or "")
        if old_id and old_id != new_id:
            _delete_block(old_id)
    return "created" if not current else "updated"


def query_subscriber_pages() -> list[dict]:
    payload: dict[str, Any] = {"page_size": 100}
    rows: list[dict] = []
    while True:
        res = _request("POST", _query_url(), json_payload=payload, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"Subscriber Decision Brief query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json()
        rows.extend(body.get("results") or [])
        if not body.get("has_more"):
            return rows
        cursor = body.get("next_cursor")
        if not cursor:
            raise RuntimeError("Subscriber Decision Brief pagination inconsistent")
        payload["start_cursor"] = cursor


def sync_subscriber_decision_briefs() -> dict[str, Any]:
    if not ENABLE_SUBSCRIBER_DECISION_BRIEF:
        return {"enabled": False, "total": 0, "created": 0, "updated": 0, "unchanged": 0, "errors": 0}
    if not NOTION_API_KEY:
        raise ValueError("Subscriber Decision Brief requires NOTION_DECISION_INTELLIGENCE_API_KEY")

    result = {"enabled": True, "total": 0, "created": 0, "updated": 0, "unchanged": 0, "errors": 0, "error_pages": []}
    for page in query_subscriber_pages():
        values = page_to_values(page)
        result["total"] += 1
        try:
            state = sync_page(values)
            result[state] += 1
        except Exception as exc:
            result["errors"] += 1
            result["error_pages"].append({"page_id": values.get("page_id"), "name": values.get("name"), "error": str(exc)[:300]})
    if result["errors"]:
        raise RuntimeError("Subscriber Decision Brief sync incomplete: " + json.dumps(result, ensure_ascii=False))
    return result


def main() -> None:
    print(json.dumps(sync_subscriber_decision_briefs(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()