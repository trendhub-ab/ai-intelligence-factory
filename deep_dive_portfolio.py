"""Deterministic Deep Dive portfolio ordering helpers.

Run238 extracts the zero-model, provider-free portfolio shaping surface from
``pipeline.py``. Runtime flags and mutable Production dependencies are supplied
by the pipeline compatibility wrappers on every call so configuration remains
live and no import-time provider, credential, persistence, or model side effect
is introduced here.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse


def topic_counts(
    items: list[dict],
    *,
    normalize_portfolio_topic: Callable[[object], str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        topic = normalize_portfolio_topic(item.get("portfolio_topic"))
        if topic == "OTHER":
            continue
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def apply_content_portfolio_balance(
    ordered: list[dict],
    visible_slots: int,
    *,
    enabled: bool,
    min_distinct_topics: int,
    priority_tolerance: float,
    evergreen_portfolio_min: int,
    normalize_portfolio_topic: Callable[[object], str],
) -> list[dict]:
    """Conservatively diversify visible slots without weakening quality/profit."""
    if not enabled or visible_slots <= 1 or len(ordered) <= 1:
        return ordered
    target = min(max(1, min_distinct_topics), visible_slots)
    if target <= 1:
        return ordered
    result = list(ordered)
    current = result[:visible_slots]
    current_topics = [normalize_portfolio_topic(item.get("portfolio_topic")) for item in current]
    if any(topic == "OTHER" for topic in current_topics):
        return result
    counts = topic_counts(current, normalize_portfolio_topic=normalize_portfolio_topic)
    if len(counts) >= target:
        return result
    cutoff = float(current[-1].get("deep_dive_priority_score", current[-1].get("score", 0)))
    evergreen_count = sum(1 for item in current if item.get("shelf_life") == "EVERGREEN")
    protected_evergreen = min(max(0, evergreen_portfolio_min), visible_slots) > 0 and evergreen_count <= 1

    for candidate_idx in range(visible_slots, len(result)):
        candidate = result[candidate_idx]
        topic = normalize_portfolio_topic(candidate.get("portfolio_topic"))
        if topic == "OTHER" or topic in counts:
            continue
        priority = float(candidate.get("deep_dive_priority_score", candidate.get("score", 0)))
        if priority + max(0.0, priority_tolerance) < cutoff:
            continue
        replace_idx = None
        current_counts = topic_counts(
            result[:visible_slots], normalize_portfolio_topic=normalize_portfolio_topic
        )
        for idx in range(visible_slots - 1, -1, -1):
            existing = result[idx]
            existing_topic = normalize_portfolio_topic(existing.get("portfolio_topic"))
            if existing_topic == "OTHER" or current_counts.get(existing_topic, 0) > 1:
                if protected_evergreen and existing.get("shelf_life") == "EVERGREEN":
                    continue
                replace_idx = idx
                break
        if replace_idx is None:
            break
        selected = result.pop(candidate_idx)
        displaced = result.pop(replace_idx)
        result.insert(replace_idx, selected)
        result.insert(candidate_idx, displaced)
        current = result[:visible_slots]
        counts = topic_counts(current, normalize_portfolio_topic=normalize_portfolio_topic)
        if len(counts) >= target:
            break
    return result


def publication_probability_score(item: dict) -> int:
    """Return the historical zero-model Ready-probability metadata proxy."""
    repo = (item or {}).get("repo", {}) or {}
    source = str(repo.get("source") or "GitHub")
    url = str(repo.get("primaryUrl") or repo.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    desc = str(repo.get("description") or "").strip()
    score = {"ArXiv": 78, "GitHub": 74, "HackerNews": 52, "ProductHunt": 50}.get(source, 48)
    if source == "ArXiv" and "arxiv.org" in host:
        score += 12
    elif source == "GitHub" and host in {"github.com", "www.github.com"}:
        score += 10
    elif source == "HackerNews" and host and "ycombinator.com" not in host:
        score += 18
    elif source == "ProductHunt" and host and "producthunt.com" not in host:
        score += 18
    if len(desc) >= 160:
        score += 8
    elif len(desc) >= 60:
        score += 5
    elif desc:
        score += 2
    if repo.get("publishedAt"):
        score += 3
    if source == "GitHub":
        spdx = str(((repo.get("licenseInfo") or {}).get("spdxId") or "")).upper()
        if spdx and spdx not in {"NOASSERTION", "UNLICENSED", "UNLICENSE"}:
            score += 3
    return max(0, min(100, int(round(score))))


def apply_publication_reliability_slot(
    ordered: list[dict],
    visible_slots: int,
    *,
    enabled: bool,
    reliability_slots: int,
    min_decision_score: float,
    min_advantage: float,
    logger: Any,
) -> list[dict]:
    if not enabled or reliability_slots <= 0 or visible_slots <= 0:
        return ordered
    for item in ordered:
        item["publication_probability_score"] = publication_probability_score(item)
    qualified = [
        (idx, item)
        for idx, item in enumerate(ordered)
        if float(item.get("score") or 0) >= min_decision_score
    ]
    if not qualified:
        return ordered
    best_idx, best = max(
        qualified,
        key=lambda pair: (
            pair[1].get("publication_probability_score", 0),
            pair[1].get("deep_dive_priority_score", 0),
            pair[1].get("score", 0),
        ),
    )
    if best_idx < visible_slots:
        return ordered
    current = ordered[:visible_slots]
    current_best_publishability = max(
        (x.get("publication_probability_score", 0) for x in current), default=0
    )
    if best.get("publication_probability_score", 0) < current_best_publishability + min_advantage:
        return ordered
    selected = ordered.pop(best_idx)
    ordered.insert(visible_slots - 1, selected)
    logger.info(
        "[PUBLICATION RELIABILITY SLOT] promoted=%s publishability=%s decision=%s",
        selected.get("repo", {}).get("nameWithOwner"),
        selected.get("publication_probability_score"),
        selected.get("score"),
    )
    return ordered


def select_stocked_deep_dive_candidates(
    screened: list[dict],
    *,
    notion_save_threshold_score: float,
    attach_profit_metadata: Callable[[dict, object, object], object],
    attach_portfolio_topic: Callable[[dict, object, object], object],
    enable_profit_priority: bool,
    profit_score_neutral: float,
    top_n_for_deep_dive: int,
    evergreen_portfolio_min: int,
    evergreen_priority_tolerance: float,
    apply_content_portfolio_balance_fn: Callable[[list[dict], int], list[dict]],
    apply_publication_reliability_slot_fn: Callable[[list[dict], int], list[dict]],
) -> list[dict]:
    """Select persisted Stock then preserve the historical profit/portfolio ordering."""
    eligible = [
        item
        for item in screened
        if item.get("score", 0) >= notion_save_threshold_score and item.get("notion_page_id")
    ]
    for item in eligible:
        attach_profit_metadata(item, item.get("commercial_score"), item.get("shelf_life_score"))
        attach_portfolio_topic(item, item.get("portfolio_topic"), item.get("raw_portfolio_topic"))

    if not enable_profit_priority:
        return sorted(
            eligible,
            key=lambda item: (
                item.get("score", 0),
                item.get("repo", {}).get("stargazerCount", 0),
            ),
            reverse=True,
        )

    ordered = sorted(
        eligible,
        key=lambda item: (
            item.get("deep_dive_priority_score", 0),
            item.get("score", 0),
            item.get("commercial_score", profit_score_neutral),
            item.get("repo", {}).get("stargazerCount", 0),
        ),
        reverse=True,
    )
    visible_slots = min(top_n_for_deep_dive, len(ordered))
    evergreen_needed = min(max(0, evergreen_portfolio_min), visible_slots)
    if evergreen_needed and visible_slots:
        current = ordered[:visible_slots]
        evergreen_count = sum(1 for item in current if item.get("shelf_life") == "EVERGREEN")
        if evergreen_count < evergreen_needed:
            cutoff = float(current[-1].get("deep_dive_priority_score", 0))
            for idx in range(visible_slots, len(ordered)):
                candidate = ordered[idx]
                if candidate.get("shelf_life") != "EVERGREEN":
                    continue
                priority = float(candidate.get("deep_dive_priority_score", 0))
                if priority + max(0.0, evergreen_priority_tolerance) < cutoff:
                    continue
                selected = ordered.pop(idx)
                ordered.insert(visible_slots - 1, selected)
                evergreen_count += 1
                if evergreen_count >= evergreen_needed:
                    break
    ordered = apply_content_portfolio_balance_fn(ordered, visible_slots)
    ordered = apply_publication_reliability_slot_fn(ordered, visible_slots)
    return ordered
