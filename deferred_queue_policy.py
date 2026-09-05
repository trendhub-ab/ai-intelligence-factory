"""Pure Deferred Deep Dive queue policy extracted from pipeline.py (Run242).

Filesystem/GitHub persistence and Notion fail-safe writes remain in pipeline.py. This module owns
only TTL, identity, serialization, validation, merge/ranking, payload shaping, and queue slicing.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable


def deferred_ttl_days(shelf_life: str, *, flash_ttl_days: int, trend_ttl_days: int, evergreen_ttl_days: int) -> int:
    return {
        "FLASH": flash_ttl_days,
        "TREND": trend_ttl_days,
        "EVERGREEN": evergreen_ttl_days,
    }.get(str(shelf_life or "TREND").upper(), trend_ttl_days)


def deferred_key(
    candidate: dict,
    *,
    candidate_identity_urls: Callable[[dict], set[str]],
    normalize_title_for_match: Callable[[str], str],
) -> str:
    repo = candidate.get("repo", {})
    urls = candidate_identity_urls(repo)
    if urls:
        return sorted(urls)[0]
    return f"{repo.get('source','')}:{normalize_title_for_match(repo.get('nameWithOwner',''))}"


def deferred_serializable(
    candidate: dict,
    *,
    ttl_days: Callable[[str], int],
    key_for_candidate: Callable[[dict], str],
    now: datetime | None = None,
) -> dict:
    repo = candidate.get("repo", {})
    current = now or datetime.now(timezone.utc)
    ttl = ttl_days(candidate.get("shelf_life"))
    safe_repo = {k: v for k, v in repo.items() if isinstance(v, (str, int, float, bool, type(None), list, dict))}
    return {
        "key": key_for_candidate(candidate), "deferred_at": current.isoformat(),
        "expires_at": (current + timedelta(days=ttl)).isoformat(), "repo": safe_repo,
        "notion_page_id": candidate.get("notion_page_id"), "score": candidate.get("score"),
        "reason": candidate.get("reason", ""), "commercial_score": candidate.get("commercial_score"),
        "shelf_life_score": candidate.get("shelf_life_score"), "shelf_life": candidate.get("shelf_life"),
        "portfolio_topic": candidate.get("portfolio_topic", "OTHER"),
        "deep_dive_priority_score": candidate.get("deep_dive_priority_score"),
    }


def valid_deferred_items(payload: object, *, max_queue: int, now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    valid: list[dict] = []
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    for row in rows:
        try:
            expiry = datetime.fromisoformat(str(row.get("expires_at", "")).replace("Z", "+00:00"))
        except Exception:
            continue
        if expiry > current and row.get("key") and isinstance(row.get("repo"), dict):
            valid.append(row)
    return valid[:max_queue]


def build_deferred_payload(items: list[dict], *, max_queue: int, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    return {"version": 1, "updated_at": current.isoformat(), "items": items[:max_queue]}


def merge_rank_deferred_candidates(
    queue: list[dict],
    candidates: list[dict],
    *,
    serialize_candidate: Callable[[dict], dict],
    max_queue: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    merged = {row.get("key"): row for row in queue if row.get("key")}
    new_rows: list[dict] = []
    for candidate in candidates:
        row = serialize_candidate(candidate)
        merged[row["key"]] = row
        new_rows.append(row)
    ranked = sorted(
        merged.values(),
        key=lambda row: (float(row.get("deep_dive_priority_score") or row.get("score") or 0), row.get("deferred_at", "")),
        reverse=True,
    )
    final = ranked[:max_queue]
    evicted = ranked[max_queue:]
    return new_rows, final, evicted, ranked


def pop_deferred_candidates(queue: list[dict], limit: int) -> tuple[list[dict], list[dict]]:
    selected = queue[:max(0, limit)]
    remaining = queue[len(selected):]
    return selected, remaining
