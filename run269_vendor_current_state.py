"""Run269 explicit current-state adapter for official vendor pages.

Some vendors expose a changelog/release feed. ByteDance/Volcengine's most reliable
commercial primary source is its official model list. Treat that as
``structured_current_state`` rather than pretending it is a release event.

Volcengine's rendered HTML is edge-dependent and can degrade to a JavaScript shell.
When that happens, Run269 may use Volcengine's own public docs fetch endpoint (the
same endpoint documented in ByteDance's official AgentKit samples) to retrieve the
same official document content. Mere reachability never qualifies as evidence.
"""
from __future__ import annotations

from html import unescape
import re
from urllib.parse import urlparse, urlunparse

import business_source_acquisition as run268
import run269_acquisition_precision as precision


_BYTEDANCE_MODEL_LIST_URL = "https://www.volcengine.com/docs/82379/1799865?lang=zh"
_BYTEDANCE_MODEL_LIST_CANONICAL_URL = "https://www.volcengine.com/docs/82379/1330310"
_VOLCENGINE_DOC_FETCH_API = "https://docs-api.cn-beijing.volces.com/api/v1/doc/fetch"

OFFICIAL_VENDOR_REGISTRY = tuple(
    (
        {
            **row,
            "release_url": _BYTEDANCE_MODEL_LIST_URL,
            "current_state_page": True,
            "current_state_label": "火山方舟 公式モデル一覧",
            "current_state_fetch_url": _BYTEDANCE_MODEL_LIST_CANONICAL_URL,
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


def _clean_official_doc_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _fetch_official_doc_content(vendor: dict, http_post) -> str:
    """Fetch the same Volcengine official doc through its public structured endpoint."""
    if not callable(http_post):
        return ""
    source_url = str(vendor.get("current_state_fetch_url") or vendor["release_url"])
    if not precision._host_allowed(source_url, tuple(vendor["allowed_domains"])):
        raise ValueError(f"official doc URL outside vendor allowlist: {source_url}")
    response = http_post(
        _VOLCENGINE_DOC_FETCH_API,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AI-Intelligence-Factory/Run269-current-state",
        },
        json={"Url": _clean_official_doc_url(source_url)},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("Result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return ""
    title = str(result.get("Title") or "").strip()
    content = str(result.get("Content") or "").strip()
    return "\n".join(part for part in (title, content) if part)


def _current_state_item(vendor: dict, html: str, normalize_item, *, transport: str):
    updated_at = _extract_recent_update(html)
    has_model_state = _has_model_list_current_state(html)
    if not updated_at and not has_model_state:
        return None

    if updated_at:
        observation = f"最近更新时间 {updated_at}。"
    else:
        observation = (
            "公式モデル一覧とSeed/Doubao系の現在モデル情報を確認。"
            "更新日時は今回の公式取得形では解決できない。"
        )

    record = {
        "title": f"{vendor.get('current_state_label') or '公式モデル一覧'} — current official state",
        "description": (
            f"公式モデル一覧の現在状態。{observation}"
            "これはリリースイベントではなく、現在のモデル選定・利用可否を確認する一次情報として扱う。"
        ),
        "url": vendor["release_url"],
        # Never fabricate a date when the official response does not expose one.
        "published_at": updated_at,
    }
    item = run268._vendor_candidate_from_record(vendor, record, normalize_item)
    details = dict(item.get("sourceDetails") or {})
    details["vendor_record_kind"] = "structured_current_state"
    details["run269_precision"] = True
    details["current_state_page"] = True
    details["current_state_timestamp_observed"] = bool(updated_at)
    details["current_state_model_markers_observed"] = bool(has_model_state)
    details["current_state_transport"] = transport
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
    details["current_state_transport"] = "official_page_html"
    normalized["sourceDetails"] = details
    return normalized


def fetch_official_vendor_updates(limit: int, *, normalize_item, http_get, http_post=None,
                                  logger=None, registry=OFFICIAL_VENDOR_REGISTRY) -> list[dict]:
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

        # Reuse the bounded visible text first; it may already contain enough evidence.
        current = _current_state_item(
            vendor,
            item.get("sourceContext") or "",
            normalize_item,
            transport="official_page_fallback_text",
        )

        # A second GET can land on a richer edge/rendering variant. Keep it bounded and
        # enforce the vendor-domain redirect allowlist.
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
                current = _current_state_item(
                    vendor,
                    html,
                    normalize_item,
                    transport="official_page_html_retry",
                )
            except Exception as exc:
                current = None
                if logger:
                    logger.warning(f"[RUN269 CURRENT STATE HTML SKIP] {vendor_name}: {exc}")

        # Final bounded fallback: Volcengine's own public structured-doc endpoint.
        # It fetches the same official document; no API key, model call, or third-party
        # evidence is introduced. The returned content must still pass strict model-list
        # evidence checks before it can become structured_current_state.
        if current is None and callable(http_post):
            try:
                official_text = _fetch_official_doc_content(vendor, http_post)
                current = _current_state_item(
                    vendor,
                    official_text,
                    normalize_item,
                    transport="official_doc_api",
                )
            except Exception as exc:
                current = None
                if logger:
                    logger.warning(f"[RUN269 CURRENT STATE DOC API SKIP] {vendor_name}: {exc}")

        if current:
            output.append(current)
            replaced.add(vendor_name)
            if logger:
                transport = (current.get("sourceDetails") or {}).get("current_state_transport")
                logger.info(f"[RUN269 CURRENT STATE] {vendor_name}: structured_current_state via {transport}")
        else:
            output.append(item)

    return output[: max(0, int(limit or 0))]
