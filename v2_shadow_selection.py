"""AIIF Rebuild V2-001 shadow-only selection core.

This module is deliberately isolated from Production authority. It performs
candidate normalization, deterministic deduplication and provider-free cheap
screening only. It does not import pipeline.py, persistence, article generation,
Notion, note delivery, or any provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

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
    """Apply deterministic, provider-free V2-001 cheap screening.

    ``now`` is an explicit input so the contract remains deterministic even
    though V2-001 does not yet apply an age-decay calculation.
    """

    del now  # Reserved for a later, explicitly designed freshness policy.

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
    if source_timestamp:
        score += 15
        reasons.append("source_timestamp_present")
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
