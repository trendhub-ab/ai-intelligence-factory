"""Run268 production overlay for business-first source strategy.

This layer retires Product Hunt from the *active* production source contract without
rewriting historical pipeline code or historical ROI state.  The old ProductHunt
function/key remains only as a compatibility call slot inside the legacy main body;
all data flowing through that slot is OfficialVendor and is renamed before screening.
"""
from __future__ import annotations

import os

from business_source_acquisition import (
    OFFICIAL_VENDOR_REGISTRY,
    SOURCE_ROLE_CONTRACT,
    fetch_hackernews_ai_reactions,
    fetch_official_vendor_updates,
)


ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")


def _positive_int(value, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def install(pipeline_module):
    """Install Run268 after historical runtime layers and before Production main()."""
    p = pipeline_module
    if bool(getattr(p, "_RUN268_BUSINESS_SOURCE_STRATEGY_INSTALLED", False)):
        return p

    legacy_producthunt_limit = _positive_int(getattr(p, "PRODUCTHUNT_FETCH_LIMIT", 50), 50)
    official_vendor_limit = _positive_int(
        os.environ.get("OFFICIAL_VENDOR_FETCH_LIMIT", legacy_producthunt_limit),
        legacy_producthunt_limit,
    )

    # Public current contract. ProductHunt is deliberately absent.
    p.SOURCE_ROLE_CONTRACT = dict(SOURCE_ROLE_CONTRACT)
    p.OFFICIAL_VENDOR_REGISTRY = tuple(OFFICIAL_VENDOR_REGISTRY)
    p.OFFICIAL_VENDOR_FETCH_LIMIT = official_vendor_limit
    p.SOURCE_ROI_SOURCES = ACTIVE_SOURCE_ORDER
    p.ENGAGEMENT_LABELS = dict(getattr(p, "ENGAGEMENT_LABELS", {}))
    p.ENGAGEMENT_LABELS["OfficialVendor"] = "N/A (official primary source)"

    original_initialize_runtime = p.initialize_runtime
    original_round_robin = p.round_robin_candidates
    original_allocate_limits = p.allocate_source_fetch_limits
    original_get_fresh_regen = getattr(p, "get_fresh_regen_test_items", None)

    def _source_base_fetch_limits_run268() -> dict[str, int]:
        return {
            "GitHub": _positive_int(getattr(p, "GITHUB_FETCH_LIMIT", 50), 50),
            "HackerNews": _positive_int(getattr(p, "HN_FETCH_LIMIT", 50), 50),
            "ArXiv": _positive_int(getattr(p, "ARXIV_FETCH_LIMIT", 50), 50),
            "OfficialVendor": _positive_int(getattr(p, "OFFICIAL_VENDOR_FETCH_LIMIT", official_vendor_limit), official_vendor_limit),
        }

    p._source_base_fetch_limits = _source_base_fetch_limits_run268

    # Rebuild ROI max limits so OfficialVendor cold-starts independently rather than
    # inheriting historical ProductHunt performance.
    multiplier = float(getattr(p, "SOURCE_ROI_MAX_FETCH_MULTIPLIER", 2.0) or 2.0)
    p.SOURCE_ROI_MAX_FETCH_BY_SOURCE = {
        source: max(base, int(round(base * multiplier)))
        for source, base in _source_base_fetch_limits_run268().items()
    }

    def allocate_source_fetch_limits_run268(*args, **kwargs):
        limits = dict(original_allocate_limits(*args, **kwargs))
        # Main body still reads source_fetch_limits["ProductHunt"]. This alias is an
        # internal call-slot only; active metrics/source identity remain OfficialVendor.
        limits["OfficialVendor"] = _positive_int(
            limits.get("OfficialVendor", official_vendor_limit), official_vendor_limit
        )
        limits["ProductHunt"] = limits["OfficialVendor"]
        return limits

    p.allocate_source_fetch_limits = allocate_source_fetch_limits_run268

    def fetch_official_vendor_run268(limit=None):
        chosen = official_vendor_limit if limit is None else _positive_int(limit, official_vendor_limit)
        return fetch_official_vendor_updates(
            chosen,
            normalize_item=p.normalize_item,
            http_get=p.requests.get,
            logger=getattr(p, "logger", None),
        )

    def fetch_hackernews_run268(limit=None):
        chosen = _positive_int(
            getattr(p, "HN_FETCH_LIMIT", 50) if limit is None else limit,
            getattr(p, "HN_FETCH_LIMIT", 50),
        )
        return fetch_hackernews_ai_reactions(
            chosen,
            normalize_item=p.normalize_item,
            http_get=p.requests.get,
            logger=getattr(p, "logger", None),
        )

    p.fetch_official_vendor_updates = fetch_official_vendor_run268
    p.fetch_hackernews_top = fetch_hackernews_run268
    # Compatibility bridge: the legacy main body calls this exact symbol. It performs
    # zero Product Hunt GraphQL/token access after Run268 installation.
    p.fetch_producthunt_trending = fetch_official_vendor_run268

    def round_robin_candidates_run268(source_groups, limit):
        # Mutate the local dict owned by the legacy main/regen path so all subsequent
        # dedupe, screening and source attribution see OfficialVendor, not ProductHunt.
        if isinstance(source_groups, dict) and "ProductHunt" in source_groups:
            legacy_items = source_groups.pop("ProductHunt") or []
            for item in legacy_items:
                if isinstance(item, dict):
                    item["source"] = "OfficialVendor"
                    details = dict(item.get("sourceDetails") or {})
                    details.setdefault("source_role", SOURCE_ROLE_CONTRACT["OfficialVendor"])
                    item["sourceDetails"] = details
            source_groups.setdefault("OfficialVendor", legacy_items)
        return original_round_robin(source_groups, limit)

    p.round_robin_candidates = round_robin_candidates_run268

    def initialize_runtime_run268(*args, **kwargs):
        # Historical preflight rejects a missing Product Hunt token. Product Hunt is no
        # longer an active source, so satisfy only that obsolete transport check with an
        # in-memory sentinel. No token is read, persisted, transmitted, or required.
        original_token = getattr(p, "PRODUCTHUNT_DEVELOPER_TOKEN", None)
        if not original_token:
            p.PRODUCTHUNT_DEVELOPER_TOKEN = "RUN268_OFFICIAL_VENDOR_NO_TOKEN_REQUIRED"
        try:
            return original_initialize_runtime(*args, **kwargs)
        finally:
            p.PRODUCTHUNT_DEVELOPER_TOKEN = original_token

    p.initialize_runtime = initialize_runtime_run268

    if callable(original_get_fresh_regen):
        def get_fresh_regen_test_items_run268(*args, **kwargs):
            # The historical function contains a literal ProductHunt key. Allow the
            # public/current source filter to be OfficialVendor while using the dormant
            # slot internally. round_robin_candidates_run268 rewrites result identity.
            if kwargs.get("source_filter") == "OfficialVendor":
                kwargs = dict(kwargs)
                kwargs["source_filter"] = "ProductHunt"
            return original_get_fresh_regen(*args, **kwargs)

        p.get_fresh_regen_test_items = get_fresh_regen_test_items_run268

    p._RUN268_BUSINESS_SOURCE_STRATEGY_INSTALLED = True
    return p
