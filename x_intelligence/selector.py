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


def _screening_score(item: Mapping[str, Any]) -> float:
    return _number(
        _first(
            item,
            "final_screening_score",
            "screening_score",
            "Screening Score",
            "raw_screening_score",
        )
    )


def _decision_score(item: Mapping[str, Any]) -> float:
    return _number(_first(item, "decision_score", "Decision Score"))


def _engagement_score(item: Mapping[str, Any]) -> float:
    """Normalize existing source engagement to 0-100 for X demand signal.

    We cap at 500 so one viral source cannot completely dominate ranking.
    No network request or new model judgment is involved.
    """

    engagement = max(0.0, _number(_first(item, "engagement", "Engagement")))
    return min(100.0, (engagement / 500.0) * 100.0)


def _freshness_bonus(item: Mapping[str, Any]) -> float:
    shelf_life = str(_first(item, "shelf_life", "Shelf Life")).upper()
    return {
        "FLASH": 12.0,
        "TREND": 10.0,
        "EVERGREEN": 5.0,
    }.get(shelf_life, 5.0)


def candidate_score(item: Mapping[str, Any]) -> float:
    """Return deterministic X suitability from existing Factory signals.

    Decision Score remains primary when present. Screening-only snapshots use a
    deliberately different weighting than article selection because X is also a
    demand-validation channel: source engagement and short-term relevance matter
    more here than they do for long-form article quality.
    """

    decision = _decision_score(item)
    screening = _screening_score(item)
    commercial = _number(
        _first(item, "commercial_value_score", "Commercial Value Score", "raw_commercial_value_score")
    )
    engagement = _engagement_score(item)
    freshness = _freshness_bonus(item)

    if decision > 0:
        score = (
            (decision * 0.55)
            + (screening * 0.20)
            + (commercial * 0.10)
            + (engagement * 0.10)
            + (freshness * 0.05)
        )
    else:
        score = (
            (screening * 0.55)
            + (commercial * 0.15)
            + (engagement * 0.20)
            + freshness
        )
    return round(score, 2)


def select_x_candidates(
    items: Iterable[Mapping[str, Any]],
    *,
    min_screening_score: float = DEFAULT_MIN_SCREENING_SCORE,
    min_decision_score: float = DEFAULT_MIN_DECISION_SCORE,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    """Select reviewable X candidates from existing Factory intelligence items."""

    if max_items <= 0:
        return []

    selected: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        url = str(_first(item, "url", "URL", "source_url", "primary_url")).strip()
        if not url:
            continue

        screening = _screening_score(item)
        decision = _decision_score(item)
        if screening < min_screening_score and decision < min_decision_score:
            continue

        item["x_candidate_score"] = candidate_score(item)
        item["x_primary_url"] = url
        item["x_screening_score"] = screening
        item["x_decision_score"] = decision
        item["x_engagement_score"] = round(_engagement_score(item), 2)
        selected.append(item)

    selected.sort(
        key=lambda item: (
            _number(item.get("x_candidate_score")),
            _number(item.get("x_decision_score")),
            _number(item.get("x_engagement_score")),
            _number(item.get("x_screening_score")),
        ),
        reverse=True,
    )
    return selected[:max_items]
