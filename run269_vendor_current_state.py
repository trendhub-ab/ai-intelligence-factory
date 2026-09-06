"""Run269 explicit current-state adapter for official vendor pages.

Some vendors expose a changelog/release feed. ByteDance/Volcengine's most reliable
server-readable commercial primary source is its official model list. Treat that as
``structured_current_state`` rather than pretending it is a release event.

Volcengine's edge/rendering shape is not stable: some HTTP responses expose the
``最近更新时间`` timestamp, while others expose only concrete model-list/navigation
content. A current-state row therefore requires either the explicit timestamp OR a
model-list-specific marker combination. Mere reachability never qualifies.
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
_MODEL_LIST_MARKERS = ("模型列表", "model list")
_MODEL_STATE_MARKERS = (
    "最新模型",
    "seed-evolving",
    "seedance",
    "seedream",
    "doubao",
    "豆包",
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


def _decoded_visible_text(html: str) -> str:
    decoded = unescape(html or "")
    decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), decoded)
    decoded = decoded.replace("\\n", "\n").replace("\\t", " ").replace('\\"', '"')
    decoded = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", decoded).strip()


def _extract_recent_update(html: str) -> str | None:
    decoded = _decoded_visible_text(html)
    match = _RECENT_UPDATE_RE.search(decoded)
    return match.group(1) if match else None


def _has_model_list_current_state(html: str) -> bool:
    """Require page-specific model evidence, never mere HTTP reachability."""
    low = _decoded_visible_text(html).casefold()
    return (
        any(marker in low for marker in _MODEL_LIST_MARKERS)
        and any(marker in low for marker in _MODEL_STATE_MARKERS)
    )


def _current_state_item(vendor: dict, html: str, normalize_item):
    updated_at = _extract_recent_update(html)
    has_model_state = _has_model_list_current_state(html)
    if not updated_at and not has_model_state:
        return None

    if updated_at:
        observation = f"最近更新时间 {updated_at}。"
    else:
        observation = (
            "公式モデル一覧とSeed/Doubao系の現在モデル情報を確認。"
            "更新日時は今回のHTTP取得形では解決できない。"
        )

    record = {
        "title": f"{vendor.get('current_state_label') or '公式モデル一覧'} — current official state",
        "description": (
            f"公式モデル一覧の現在状態。{observation}"
            "これはリリースイベントではなく、現在のモデル選定・利用可否を確認する一次情報として扱う。"
        ),
        "url": vendor["release_url"],
        # Never fabricate a date when the response variant does not expose one.
        "published_at": updated_at,
    }
    item = run268._vendor_candidate_from_record(vendor, record, normalize_item)
    details = dict(item.get("sourceDetails") or {})
    details["vendor_record_kind"] = "structured_current_state"
    details["run269_precision"] = True
    details["current_state_page"] = True
    details["current_state_timestamp_observed"] = bool(updated_at)
    details["current_state_model_markers_observed"] = bool(has_model_state)
    item["sourceDetails"] = details
    return item


def _normalize_existing_current_state(item: dict) -> dict:
    """A structured row from a declared model-list page is state, not a release."""
    normalized = dict(item)
    details = dict(item.get("sourceDetails") or {})
    details["vendor_record_kind"] = "structured_current_state"
    details["run269_precision"] = True
    details["current_state_page"] = True
    details["current_state_timestamp_observed"] = bool(item.get("publishedAt"))
    details["current_state_model_markers_observed"] = True
    normalized["sourceDetails"] = details
    return normalized


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
        if kind.startswith("structured_"):
            output.append(_normalize_existing_current_state(item))
            continue
        if kind != "page_fallback":
            output.append(item)
            continue
        if vendor_name in replaced:
            continue

        # The precision fallback already carries bounded visible text. Reuse it first;
        # this avoids depending on a second request returning the same edge/render shape.
        current = _current_state_item(vendor, item.get("sourceContext") or "", normalize_item)
        if current is None:
            try:
                response = http_get(
                    vendor["release_url"],
                    timeout=12,
                    headers={"User-Agent": "AI-Intelligence-Factory/Run269-current-state"},
                )
                final_url = str(getattr(response, "url", "") or vendor["release_url"])
                if not precision._host_allowed(final_url, tuple(vendor["allowed_domains"])):
                    raise ValueError(f"redirected outside vendor allowlist: {final_url}")
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
