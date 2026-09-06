"""Run269 Production overlay for live source-acquisition precision.

Install after Run268. Run268 remains the source/business architecture authority;
Run269 only replaces the two live acquisition functions that real-network smoke
proved needed stricter precision.
"""
from __future__ import annotations

from run269_vendor_current_state import (
    HN_AI_QUERIES,
    HN_LOOKBACK_DAYS,
    OFFICIAL_VENDOR_REGISTRY,
    fetch_hackernews_ai_reactions,
    fetch_official_vendor_updates,
)


def _positive_int(value, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def install(pipeline_module):
    p = pipeline_module
    if bool(getattr(p, "_RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED", False)):
        return p

    # Run231 and other orchestration tests use intentionally tiny pipeline doubles.
    # If the network/normalization capabilities are absent, this overlay is a no-op.
    required = ("normalize_item", "requests")
    if any(not hasattr(p, name) for name in required):
        return p

    official_limit = _positive_int(getattr(p, "OFFICIAL_VENDOR_FETCH_LIMIT", 50), 50)
    hn_limit = _positive_int(getattr(p, "HN_FETCH_LIMIT", 50), 50)

    p.OFFICIAL_VENDOR_REGISTRY = tuple(OFFICIAL_VENDOR_REGISTRY)
    p.HN_AI_QUERIES = tuple(HN_AI_QUERIES)
    p.HN_LOOKBACK_DAYS = HN_LOOKBACK_DAYS

    def fetch_official_vendor_run269(limit=None):
        chosen = official_limit if limit is None else _positive_int(limit, official_limit)
        return fetch_official_vendor_updates(
            chosen,
            normalize_item=p.normalize_item,
            http_get=p.requests.get,
            logger=getattr(p, "logger", None),
        )

    def fetch_hackernews_run269(limit=None):
        chosen = hn_limit if limit is None else _positive_int(limit, hn_limit)
        return fetch_hackernews_ai_reactions(
            chosen,
            normalize_item=p.normalize_item,
            http_get=p.requests.get,
            logger=getattr(p, "logger", None),
        )

    p.fetch_official_vendor_updates = fetch_official_vendor_run269
    p.fetch_hackernews_top = fetch_hackernews_run269
    # The historical main body still calls the retired ProductHunt symbol. Run268 made
    # it an OfficialVendor compatibility slot; Run269 upgrades that same slot's quality.
    p.fetch_producthunt_trending = fetch_official_vendor_run269

    p._RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED = True
    return p
