"""Deterministic candidate selection for the X output layer.

No Gemini calls, no X API calls, and no writes to the article pipeline.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


DEFAULT_MIN_SCREENING_SCORE = 55
DEFAULT_MIN_DECISION_SCORE = 60
DEFAULT_MAX_ITEMS = 5


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(item: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default


def candidate_score(item: Mapping[str, Any]) -> float:
    """Return a deterministic X suitability score from existing Factory data.

    Decision value remains primary, while screening/engagement provide a small
    tie-break. This deliberately avoids replacing the Factory's article quality
    logic with a new hidden model.
    """

    decision = _number(_first(item, "decision_score", "Decision Score"))
    screening = _number(_first(item, "screening_score", "Screening Score"))
    engagement = _number(_first(item, "engagement", "Engagement"))
    return round((decision * 0.65) + (screening * 0.30) + (min(engagement, 100.0) * 0.05), 2)


def select_x_candidates(
    items: Iterable[Mapping[str, Any]],
    *,
    min_screening_score: float = DEFAULT_MIN_SCREENING_SCORE,
    min_decision_score: float = DEFAULT_MIN_DECISION_SCORE,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    """Select reviewable X candidates from existing Factory intelligence items.

    Fail-closed rules:
    - a source URL is mandatory;
    - items below both screening and decision thresholds are excluded;
    - no external API is called;
    - input objects are never mutated.
    """

    if max_items <= 0:
        return []

    selected: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        url = str(_first(item, "url", "URL", "source_url", "primary_url")).strip()
        if not url:
            continue

        screening = _number(_first(item, "screening_score", "Screening Score"))
        decision = _number(_first(item, "decision_score", "Decision Score"))
        if screening < min_screening_score and decision < min_decision_score:
            continue

        item["x_candidate_score"] = candidate_score(item)
        item["x_primary_url"] = url
        selected.append(item)

    selected.sort(
        key=lambda item: (
            _number(item.get("x_candidate_score")),
            _number(_first(item, "decision_score", "Decision Score")),
            _number(_first(item, "screening_score", "Screening Score")),
        ),
        reverse=True,
    )
    return selected[:max_items]
