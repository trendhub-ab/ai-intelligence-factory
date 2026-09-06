"""Run269 explicit current-state adapter for official vendor pages.

Some vendors expose a changelog/release feed. ByteDance/Volcengine's most reliable
server-readable commercial primary source is its official model list, whose page
carries an explicit recent-update timestamp. Treat that as ``structured_current_state``
rather than pretending it is a release event.
"""
from __future__ import annotations

from html import unescape
import re

import business_source_acquisition as run268
import run269_acquisition_precision as precision


_BYTEDANCE_MODEL_LIST_URL = "https://www.volcengine.com/docs/82379/1799865?lang=zh"

OFFICIAL_VENDOR_REGISTRY = tuple(
    (
        {
            **row,
            "release_url": _BYTEDANCE_MODEL_LIST_URL,
            "current_state_page": True,
            "current_state_label": "火山方舟 公式モデル一覧",
        }
        if row["vendor"] == "ByteDance Doubao/Seed"
        else row
    )
    for row in precision.OFFICIAL_VENDOR_REGISTRY
)

HN_AI_QUERIES = precision.HN_AI_QUERIES
HN_LOOKBACK_DAYS = precision.HN_LOOKBACK_DAYS
fetch_hackernews_ai_reactions = precision.fetch_hackernews_ai_reactions

_RECENT_UPDATE_RE = re.compile(
    r"最近更新(?:时间|時間)?\s*[：:]?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2})",
    re.I,
)


def _response_text(response) -> str:
    response.raise_for_status()
    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content or "")


def _extract_recent_update(html: str) -> str | None:
    decoded = unescape(html or "")
    decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), decoded)
    decoded = decoded.replace("\\n", "\n").replace("\\t", " ").replace('\\"', '"')
    decoded = re.sub(r"<[^>]+>", " ", decoded)
    decoded = re.sub(r"\s+", " ", decoded)
    match = _RECENT_UPDATE_RE.search(decoded)
    return match.group(1) if match else None


def _current_state_item(vendor: dict, html: str, normalize_item):
    updated_at = _extract_recent_update(html)
    if not updated_at:
        return None
    record = {
        "title": f"{vendor.get('current_state_label') or '公式モデル一覧'} — current official state",
        "description": (
            f"公式モデル一覧の現在状態。最近更新时间 {updated_at}。"
            "これはリリースイベントではなく、現在のモデル選定・利用可否を確認する一次情報として扱う。"
        ),
        "url": vendor["release_url"],
        "published_at": updated_at,
    }
    item = run268._vendor_candidate_from_record(vendor, record, normalize_item)
    details = dict(item.get("sourceDetails") or {})
    details["vendor_record_kind"] = "structured_current_state"
    details["run269_precision"] = True
    details["current_state_page"] = True
    item["sourceDetails"] = details
    return item


def fetch_official_vendor_updates(limit: int, *, normalize_item, http_get, logger=None,
                                  registry=OFFICIAL_VENDOR_REGISTRY) -> list[dict]:
    """Use precision extraction, with an explicit current-state path where declared."""
    rows = precision.fetch_official_vendor_updates(
        limit,
        normalize_item=normalize_item,
        http_get=http_get,
        logger=logger,
        registry=registry,
    )

    by_vendor = {row["vendor"]: row for row in registry}
    output: list[dict] = []
    replaced: set[str] = set()
    for item in rows:
        details = item.get("sourceDetails") or {}
        vendor_name = details.get("vendor") or ""
        vendor = by_vendor.get(vendor_name)
        if not vendor or not vendor.get("current_state_page"):
            output.append(item)
            continue
        kind = details.get("vendor_record_kind") or ""
        if kind != "page_fallback":
            output.append(item)
            continue
        if vendor_name in replaced:
            continue
        try:
            response = http_get(
                vendor["release_url"],
                timeout=12,
                headers={"User-Agent": "AI-Intelligence-Factory/Run269-current-state"},
            )
            html = _response_text(response)
            current = _current_state_item(vendor, html, normalize_item)
        except Exception as exc:
            current = None
            if logger:
                logger.warning(f"[RUN269 CURRENT STATE SKIP] {vendor_name}: {exc}")
        if current:
            output.append(current)
            replaced.add(vendor_name)
            if logger:
                logger.info(f"[RUN269 CURRENT STATE] {vendor_name}: structured_current_state")
        else:
            output.append(item)

    return output[: max(0, int(limit or 0))]
