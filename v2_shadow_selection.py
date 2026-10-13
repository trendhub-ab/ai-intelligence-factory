"""AIIF Rebuild V2-001 shadow-only selection core.

This module is deliberately isolated from Production authority. It performs
candidate normalization, deterministic deduplication, provider-free cheap
screening, a one-shot Deep Dive decision, and read-only V1 comparison. It does
not import pipeline.py, persistence, article generation, Notion, note delivery,
or any provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from typing import Any, Callable, Iterable, Mapping

from candidate_identity import canonicalize_url


DEFAULT_MIN_SCREENING_SCORE = 40


@dataclass(frozen=True)
class ShadowConfig:
    """Bounded defaults for the V2-001 shadow slice."""

    max_candidates_per_provider: int = 10
    max_deep_dive_attempts: int = 1
    min_screening_score: int = DEFAULT_MIN_SCREENING_SCORE


def _first_text(raw: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _timestamp_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _freshness_signal(value: Any, *, now: datetime) -> tuple[int, str | None]:
    """Return a small deterministic freshness bonus without making age a hard gate.

    V2-001 is selection-only, so stale items remain eligible when their other
    evidence is strong. Freshness only influences ordering. Timestamps must be
    timezone-aware ISO-8601 values; malformed or materially future timestamps
    receive no freshness credit.
    """

    if not value:
        return 0, None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0, "source_timestamp_invalid"
    if parsed.tzinfo is None or now.tzinfo is None:
        return 0, "source_timestamp_invalid"

    try:
        age_seconds = (
            now.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)
        ).total_seconds()
    except (OverflowError, ValueError):
        return 0, "source_timestamp_invalid"

    if age_seconds < -86400:
        return 0, "source_timestamp_future"
    if age_seconds <= 7 * 86400:
        return 15, "fresh_within_7d"
    if age_seconds <= 30 * 86400:
        return 8, "recent_within_30d"
    return 0, "stale_over_30d"


def normalize_candidate(
    raw: Mapping[str, Any],
    *,
    provider: str,
    acquired_at: datetime,
) -> dict[str, Any]:
    """Convert a provider payload into the V2 shadow candidate contract.

    V2-001 intentionally requires both a usable URL and title. When either is
    absent, the candidate is rejected rather than inventing an identity.
    """

    if not isinstance(raw, Mapping):
        raise ValueError("candidate must be a mapping")

    primary_url = _first_text(raw, "primary_url", "primaryUrl", "url")
    title = _first_text(raw, "title", "name")
    identity = canonicalize_url(primary_url)
    if not primary_url or not title or not identity:
        raise ValueError("candidate requires a valid URL and title")

    description = _first_text(raw, "description", "summary", "snippet")
    source_timestamp = _timestamp_text(
        raw.get("published_at")
        if raw.get("published_at") is not None
        else raw.get("publishedAt")
        if raw.get("publishedAt") is not None
        else raw.get("source_timestamp")
    )

    return {
        "candidate_identity": identity,
        "provider": str(provider or "").strip(),
        "primary_url": primary_url,
        "title": title,
        "description": description,
        "source_timestamp": source_timestamp,
        "acquired_at": acquired_at.isoformat(),
        "evidence_sufficiency": "unassessed",
    }


def deduplicate_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first candidate for each stable identity, preserving input order."""

    seen: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = str(candidate.get("candidate_identity") or "").strip()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(dict(candidate))
    return deduplicated


def screen_candidate(
    candidate: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Apply deterministic, provider-free V2-001 cheap screening."""

    result = dict(candidate)
    score = 0
    reasons: list[str] = []

    identity = str(candidate.get("candidate_identity") or "").strip()
    title = str(candidate.get("title") or "").strip()
    description = str(candidate.get("description") or "").strip()
    provider = str(candidate.get("provider") or "").strip().lower()
    source_timestamp = candidate.get("source_timestamp")

    if identity:
        score += 20
        reasons.append("stable_identity")
    if title:
        score += 15
        reasons.append("title_present")
    if len(description) >= 60:
        score += 20
        reasons.append("description_substantive")
    elif len(description) >= 20:
        score += 10
        reasons.append("description_present")

    freshness_score, freshness_reason = _freshness_signal(source_timestamp, now=now)
    score += freshness_score
    if freshness_reason:
        reasons.append(freshness_reason)

    if provider in {"officialvendor", "official", "official_vendor"}:
        score += 20
        reasons.append("official_source")

    result["screening_score"] = int(score)
    result["screening_reasons"] = reasons
    result["eligible"] = score >= DEFAULT_MIN_SCREENING_SCORE
    return result


def rank_candidates(
    candidates: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Screen then rank deterministically by score and stable identity."""

    screened = [screen_candidate(candidate, now=now) for candidate in candidates]
    return sorted(
        screened,
        key=lambda item: (
            -int(item.get("screening_score") or 0),
            str(item.get("candidate_identity") or ""),
        ),
    )


def _comparison_identity(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return canonicalize_url(text) if "://" in text else text


def _comparison_status(winner: str | None, v1_reference: str | None) -> str:
    if winner is None:
        return "v2_no_winner"
    reference = _comparison_identity(v1_reference)
    if reference is None:
        return "unavailable"
    return "same" if winner == reference else "different"


def run_shadow_selection(
    *,
    providers: Mapping[str, Callable[[], Iterable[Mapping[str, Any]]]],
    deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    config: ShadowConfig,
    now: datetime,
    run_id: str,
    v1_reference: str | None = None,
) -> dict[str, Any]:
    """Run the V2-001 selection slice without granting Production authority.

    Provider callables and the Deep Dive callable are injected so the core has
    no network/provider dependency. A run may call each provider once and may
    attempt Deep Dive at most once. It never falls back to rank 2 after a Deep
    Dive failure or evidence-insufficient result.
    """

    max_per_provider = max(0, int(config.max_candidates_per_provider))
    deep_dive_budget = 1 if int(config.max_deep_dive_attempts) > 0 else 0
    min_score = int(config.min_screening_score)

    provider_statuses: dict[str, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    acquired_count = 0
    provider_calls = 0
    successful_providers = 0

    for provider_name, provider in providers.items():
        name = str(provider_name)
        provider_calls += 1
        status: dict[str, Any] = {
            "status": "success",
            "accepted_count": 0,
            "normalized_count": 0,
            "rejected_count": 0,
        }
        try:
            raw_items = provider()
            bounded_items = list(islice(iter(raw_items), max_per_provider))
            successful_providers += 1
            status["accepted_count"] = len(bounded_items)
            acquired_count += len(bounded_items)
            for raw in bounded_items:
                try:
                    candidate = normalize_candidate(raw, provider=name, acquired_at=now)
                except (TypeError, ValueError):
                    status["rejected_count"] += 1
                    continue
                normalized.append(candidate)
                status["normalized_count"] += 1
        except Exception as exc:  # provider boundary: isolate failures, never expose messages
            status = {
                "status": "failure",
                "accepted_count": 0,
                "normalized_count": 0,
                "rejected_count": 0,
                "error_category": type(exc).__name__,
            }
        provider_statuses[name] = status

    deduplicated = deduplicate_candidates(normalized)
    ranked = rank_candidates(deduplicated, now=now)
    for candidate in ranked:
        candidate["eligible"] = int(candidate.get("screening_score") or 0) >= min_score
    eligible = [candidate for candidate in ranked if candidate["eligible"]]

    deep_dive_attempted_count = 0
    deep_dive_result_category = "not_attempted"
    winner: str | None = None
    failure_category: str | None = None

    if not eligible:
        failure_category = "all_providers_failed" if providers and successful_providers == 0 else "insufficient_evidence"
    elif deep_dive_budget == 0:
        failure_category = "insufficient_evidence"
    else:
        top = eligible[0]
        deep_dive_attempted_count = 1
        try:
            result = deep_dive(top)
        except Exception:
            deep_dive_result_category = "provider_failure"
            failure_category = "deep_dive_failure"
        else:
            if isinstance(result, Mapping) and result.get("evidence_sufficient") is True:
                winner = str(top["candidate_identity"])
                deep_dive_result_category = "sufficient"
            elif isinstance(result, Mapping):
                deep_dive_result_category = "insufficient_evidence"
                failure_category = "insufficient_evidence"
            else:
                deep_dive_result_category = "invalid_result"
                failure_category = "deep_dive_failure"

    reference_identity = _comparison_identity(v1_reference)
    comparison_status = _comparison_status(winner, v1_reference)
    screening_summary = [
        {
            "candidate_identity": candidate["candidate_identity"],
            "provider": candidate["provider"],
            "screening_score": candidate["screening_score"],
            "screening_reasons": list(candidate["screening_reasons"]),
            "eligible": bool(candidate["eligible"]),
        }
        for candidate in ranked
    ]

    return {
        "run_id": str(run_id),
        "timestamp": now.isoformat(),
        "mode": "shadow",
        "provider_statuses": provider_statuses,
        "acquired_candidate_count": acquired_count,
        "normalized_candidate_count": len(normalized),
        "deduplicated_candidate_count": len(deduplicated),
        "screened_candidate_count": len(ranked),
        "screening": screening_summary,
        "deep_dive_attempted_count": deep_dive_attempted_count,
        "deep_dive_result_category": deep_dive_result_category,
        "v2_selected_candidate_identity": winner,
        "v1_reference_identity": reference_identity,
        "comparison_status": comparison_status,
        "failure_category": failure_category,
        "budgets": {
            "max_candidates_per_provider": max_per_provider,
            "max_deep_dive_attempts": deep_dive_budget,
            "min_screening_score": min_score,
        },
        "actual_calls": {
            "provider": provider_calls,
            "deep_dive": deep_dive_attempted_count,
        },
    }
