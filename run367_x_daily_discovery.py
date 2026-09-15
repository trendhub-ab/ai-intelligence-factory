"""Run367: wire bounded X discovery into Production Daily ``full``.

X is a discovery signal only.  Raw posts never become Evidence or article source
context.  The overlay resolves external URLs through the isolated x_discovery
pipeline, converts only conservative primary-source candidates into normal Factory
candidates, and fails open so an X/Apify outage cannot stop the four established
Production sources.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from x_discovery.providers import ApifyProvider
from x_discovery.runner import run_ingestion


X_SOURCE = "X"
X_SOURCE_ROLE = "discovery_signal"
DEFAULT_ACTOR_ID = "simple.actor~x-profile-posts"
DEFAULT_MAX_CHARGE_USD = 0.05
DEFAULT_MAX_RECORDS = 100
DEFAULT_MAX_POSTS_PER_PROFILE = 5
DEFAULT_LOOKBACK = "12 hours"
WATCHLIST_PATH = Path(__file__).resolve().parent / "x_discovery" / "watchlists" / "ai_core_20.json"
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_REQUIRED_RUNTIME_CAPABILITIES = ("round_robin_candidates", "normalize_item")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: object, default: int, *, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    parsed = max(1, parsed)
    return min(parsed, maximum) if maximum is not None else parsed


def _bounded_float(value: object, default: float, *, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if parsed <= 0:
        parsed = float(default)
    return min(parsed, maximum)


def _logger(pipeline_module):
    return getattr(pipeline_module, "logger", logging.getLogger(__name__))


def _enabled() -> bool:
    # Explicit opt-in prevents validation/recovery entrypoints from making paid X calls.
    return _truthy(os.getenv("AIIF_X_DISCOVERY_ENABLED")) and os.getenv("AIIF_RUN_MODE", "full") == "full"


def _load_watchlist(path: Path = WATCHLIST_PATH) -> tuple[str, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    accounts = payload.get("accounts") if isinstance(payload, dict) else None
    handles = tuple(
        str(row.get("handle") or "").strip().lstrip("@")
        for row in (accounts or [])
        if isinstance(row, Mapping) and str(row.get("handle") or "").strip()
    )
    if len(handles) != 20 or len({item.casefold() for item in handles}) != 20:
        raise ValueError("X Daily watchlist must contain exactly 20 unique handles")
    return handles


def build_actor_input(handles: Iterable[str]) -> dict:
    handles = [str(item).strip().lstrip("@") for item in handles if str(item).strip()]
    if len(handles) != 20 or len({item.casefold() for item in handles}) != 20:
        raise ValueError("X Daily actor input requires exactly 20 unique handles")
    return {
        "handles": handles,
        "outputFormat": "profile",
        "maxPosts": DEFAULT_MAX_POSTS_PER_PROFILE,
        "onlyPostsNewerThan": DEFAULT_LOOKBACK,
        "includeRaw": False,
        "isolateProfiles": True,
    }


def canonical_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return raw
    query = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered.startswith("utm_") or lowered in _TRACKING_KEYS:
            continue
        query.append((key, val))
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.casefold(), path, urlencode(query, doseq=True), ""))


def _candidate_title(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.removeprefix("www.")
    segment = unquote(parts.path.rstrip("/").split("/")[-1]) if parts.path.rstrip("/") else ""
    segment = re.sub(r"[-_]+", " ", segment)
    segment = re.sub(r"\s+", " ", segment).strip()
    if not segment or segment.casefold() in {"index", "home"}:
        return host
    return f"{segment[:120]} — {host}"


def queue_to_factory_candidates(pipeline_module, queue: Mapping[str, object]) -> list[dict]:
    """Convert inert primary-resolution queue items into screening candidates.

    No X post text is copied into ``description`` or ``sourceContext``.  The only
    content-bearing URL is the resolved external primary-source candidate.
    """
    if queue.get("queue_type") != "x_primary_source_resolution":
        raise ValueError("unexpected X handoff queue type")
    if queue.get("evidence_status") != "discovery_only" or queue.get("factory_write") is not False:
        raise ValueError("X handoff violated discovery-only contract")

    items: list[dict] = []
    for row in queue.get("items") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("is_evidence") is not False or row.get("source_role") != X_SOURCE_ROLE:
            continue
        url = canonical_url(row.get("canonical_url"))
        if not url:
            continue
        authors = [str(value).strip().lstrip("@") for value in (row.get("authors") or []) if str(value).strip()]
        post_urls = [str(value).strip() for value in (row.get("x_post_urls") or []) if str(value).strip()]
        post_ids = [str(value).strip() for value in (row.get("x_post_ids") or []) if str(value).strip()]
        details = {
            "source_platform": "x",
            "source_role": X_SOURCE_ROLE,
            "raw_source_not_evidence": True,
            "evidence_status": "discovery_only",
            "is_evidence": False,
            "canonical_primary_url": url,
            "resolution_status": str(row.get("resolution_status") or "candidate_needs_primary_verification"),
            "x_source_authors": authors,
            "x_source_post_urls": post_urls,
            "x_source_post_ids": post_ids,
            "mention_count": int(row.get("mention_count") or 1),
        }
        candidate = pipeline_module.normalize_item(
            X_SOURCE,
            _candidate_title(url),
            url,
            "X監視で発見した一次情報候補URL。X投稿自体は根拠に使わず、リンク先一次情報だけを検証対象とする。",
            int(row.get("mention_count") or 1),
            license_info=None,
            published_at=None,
            source_context="",
            primary_url=url,
            source_details=details,
        )
        items.append(candidate)
    return items


def acquire_x_candidates(pipeline_module) -> list[dict]:
    """Perform one bounded live X acquisition, returning zero items on degradation."""
    log = _logger(pipeline_module)
    if not _enabled():
        return []

    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        log.warning("[X DISCOVERY DEGRADED] APIFY_TOKEN missing; continuing with established sources")
        return []

    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_ACTOR_ID).strip() or DEFAULT_ACTOR_ID
    if actor_id != DEFAULT_ACTOR_ID:
        log.warning("[X DISCOVERY DEGRADED] unexpected actor id=%s; continuing without X", actor_id)
        return []

    max_charge = _bounded_float(
        os.getenv("APIFY_MAX_CHARGE_USD", DEFAULT_MAX_CHARGE_USD),
        DEFAULT_MAX_CHARGE_USD,
        maximum=DEFAULT_MAX_CHARGE_USD,
    )
    max_records = _positive_int(
        os.getenv("X_DISCOVERY_MAX_RECORDS", DEFAULT_MAX_RECORDS),
        DEFAULT_MAX_RECORDS,
        maximum=DEFAULT_MAX_RECORDS,
    )

    try:
        handles = _load_watchlist()
        provider = ApifyProvider(
            token=token,
            actor_id=actor_id,
            actor_input=build_actor_input(handles),
            max_total_charge_usd=max_charge,
        )
        with tempfile.TemporaryDirectory(prefix="aiif-x-daily-") as tmp:
            root = Path(tmp)
            manifest = run_ingestion(
                provider,
                output_dir=root,
                max_records=max_records,
                resolve_tco=True,
            )
            queue = json.loads((root / "primary_resolution_queue.json").read_text(encoding="utf-8"))
        candidates = queue_to_factory_candidates(pipeline_module, queue)
        pipeline_module.X_DISCOVERY_LAST_MANIFEST = dict(manifest)
        log.info(
            "[X DISCOVERY DAILY] profiles=%s signals=%s primary=%s provider_errors=%s external_calls=%s factory_candidates=%s",
            manifest.get("requested_profile_count", 0),
            manifest.get("new_signal_count", 0),
            manifest.get("primary_resolution_queue_count", 0),
            manifest.get("provider_error_count", 0),
            manifest.get("external_provider_calls", 0),
            len(candidates),
        )
        return candidates
    except Exception as exc:  # X is additive; never take down the established source set.
        log.warning("[X DISCOVERY DEGRADED] %s; continuing with established sources", exc)
        pipeline_module.X_DISCOVERY_LAST_ERROR = str(exc)
        return []


def _existing_urls(source_groups: Mapping[str, object]) -> set[str]:
    seen: set[str] = set()
    for source, rows in source_groups.items():
        if source == X_SOURCE or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            for key in ("primaryUrl", "url"):
                value = canonical_url(row.get(key))
                if value:
                    seen.add(value)
    return seen


def install(pipeline_module):
    """Install after Run268/269; inject X only into explicit Production ``full``."""
    p = pipeline_module
    if bool(getattr(p, "_RUN367_X_DAILY_DISCOVERY_INSTALLED", False)):
        return p
    if not all(hasattr(p, name) for name in _REQUIRED_RUNTIME_CAPABILITIES):
        return p

    role_contract = dict(getattr(p, "SOURCE_ROLE_CONTRACT", {}))
    role_contract[X_SOURCE] = X_SOURCE_ROLE
    p.SOURCE_ROLE_CONTRACT = role_contract
    p.ENGAGEMENT_LABELS = dict(getattr(p, "ENGAGEMENT_LABELS", {}))
    p.ENGAGEMENT_LABELS[X_SOURCE] = "Primary-source URL mentions discovered via X"

    original_round_robin = p.round_robin_candidates
    cache: dict[str, object] = {"loaded": False, "items": []}

    def round_robin_candidates_run367(source_groups, limit):
        if not isinstance(source_groups, dict) or not _enabled():
            return original_round_robin(source_groups, limit)

        if not cache["loaded"]:
            cache["items"] = list(acquire_x_candidates(p))
            cache["loaded"] = True

        existing = _existing_urls(source_groups)
        x_items: list[dict] = []
        duplicate_count = 0
        local_seen: set[str] = set()
        for item in cache["items"]:
            if not isinstance(item, dict):
                continue
            url = canonical_url(item.get("primaryUrl") or item.get("url"))
            if not url or url in existing or url in local_seen:
                duplicate_count += 1
                continue
            local_seen.add(url)
            x_items.append(item)

        if x_items:
            source_groups[X_SOURCE] = x_items
        _logger(p).info(
            "[X DISCOVERY MERGE] accepted=%s duplicate_before_screening=%s enabled=true",
            len(x_items),
            duplicate_count,
        )
        return original_round_robin(source_groups, limit)

    p.round_robin_candidates = round_robin_candidates_run367
    p._RUN367_X_DAILY_DISCOVERY_INSTALLED = True
    return p


install_x_daily_discovery = install
