"""Run225 — zero-model Screening Stock lifecycle policy.

Screening Stock is a historical asset, not an ever-growing active queue.  This
module classifies records without Gemini/model calls and without mutating
Decision Score, Adoption state, Evidence, or source content.

Lifecycle:
- Fresh: 0..30 days
- Aging: 31..90 days, or missing/invalid freshness date (fail-safe visible state)
- Evergreen: >90 days only for durable GitHub/arXiv assets that do not look like
  a transient event/news item
- Archive: >90 days for time-sensitive/discovery stock

Archive means "remove from active recommendation/review surfaces", never delete.
A later first-party update or human review can move an item back to Fresh because
classification is recomputed from the newest authoritative freshness anchor.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

FRESH_DAYS = max(1, int(os.environ.get("STOCK_FRESH_DAYS", "30")))
ARCHIVE_DAYS = max(FRESH_DAYS + 1, int(os.environ.get("STOCK_ARCHIVE_DAYS", "90")))

FRESH = "Fresh"
AGING = "Aging"
EVERGREEN = "Evergreen"
ARCHIVE = "Archive"
ACTIVE_LIFECYCLES = {FRESH, AGING, EVERGREEN}
DURABLE_SOURCES = {"GitHub", "ArXiv"}

# Deliberately narrow.  False positives here would wrongly hide durable assets,
# so only explicit event/ephemeral language is treated as time-sensitive.
_EVENT_PATTERNS = (
    r"\bincident\b",
    r"\boutage\b",
    r"\bcompromise(?:d)?\b",
    r"\bhack(?:ed|ing)?\b",
    r"\bacquir(?:e|ed|es|ing|isition)\b",
    r"\bjoining\b",
    r"\bprice(?:s|d|ing)?\b",
    r"\bcharges?\b",
    r"\blaunch(?:ed|es|ing)?\b",
    r"\brelease(?:d|s)? today\b",
    r"\bask hn\b",
    r"\brant\b",
    r"障害",
    r"インシデント",
    r"買収",
    r"値上げ",
    r"価格改定",
    r"本日(?:公開|発表|提供)",
)


@dataclass(frozen=True)
class LifecycleDecision:
    label: str
    age_days: int | None
    anchor: str
    reason: str

    @property
    def active(self) -> bool:
        return self.label in ACTIVE_LIFECYCLES


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_sources(source: str | Iterable[str] | None) -> set[str]:
    if source is None:
        return set()
    if isinstance(source, str):
        values = re.split(r"[,/|]", source)
    else:
        values = [str(x) for x in source]
    return {value.strip() for value in values if value and value.strip()}


def is_transient_event(name: str = "", summary: str = "") -> bool:
    text = f"{name or ''} {summary or ''}"
    return any(re.search(pattern, text, re.I) for pattern in _EVENT_PATTERNS)


def classify_lifecycle(
    *,
    source: str | Iterable[str] | None = None,
    published_at: str | datetime | None = None,
    analyzed_at: str | datetime | None = None,
    reviewed_at: str | datetime | None = None,
    name: str = "",
    summary: str = "",
    now: datetime | None = None,
) -> LifecycleDecision:
    """Return a deterministic lifecycle decision.

    `reviewed_at` is intentionally the strongest anchor.  A human/current product
    review can make an old source current again.  Raw Screening Stock should omit
    `reviewed_at`, so source publication time remains authoritative there.
    """
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    anchors = (
        ("reviewed_at", reviewed_at),
        ("published_at", published_at),
        ("analyzed_at", analyzed_at),
    )
    anchor_name = ""
    anchor_dt = None
    for candidate_name, candidate_value in anchors:
        parsed = parse_datetime(candidate_value)
        if parsed is not None:
            anchor_name = candidate_name
            anchor_dt = parsed
            break

    # Missing date must not be guessed as Fresh.  Aging keeps it visible while
    # preventing an unknown-age item from receiving a freshness bonus.
    if anchor_dt is None:
        return LifecycleDecision(AGING, None, "missing", "freshness_date_missing_fail_safe")

    age_days = max(0, (now_utc - anchor_dt).days)
    if age_days <= FRESH_DAYS:
        return LifecycleDecision(FRESH, age_days, anchor_name, f"age<={FRESH_DAYS}d")
    if age_days <= ARCHIVE_DAYS:
        return LifecycleDecision(
            AGING, age_days, anchor_name, f"{FRESH_DAYS}<age<={ARCHIVE_DAYS}d"
        )

    sources = normalize_sources(source)
    durable = bool(sources & DURABLE_SOURCES)
    transient = is_transient_event(name, summary)
    if durable and not transient:
        return LifecycleDecision(
            EVERGREEN,
            age_days,
            anchor_name,
            "durable_github_or_arxiv_asset_without_event_signal",
        )
    return LifecycleDecision(
        ARCHIVE,
        age_days,
        anchor_name,
        "older_than_active_window_and_not_durable_evergreen",
    )


def classify_record(record, *, now: datetime | None = None, prefer_review: bool = False) -> LifecycleDecision:
    """Adapter for TechnologyRecord-like objects used by portfolio planning."""
    return classify_lifecycle(
        source=getattr(record, "source", None),
        published_at=getattr(record, "published_at", None),
        analyzed_at=getattr(record, "analyzed_at", None),
        reviewed_at=getattr(record, "last_reviewed", None) if prefer_review else None,
        name=str(getattr(record, "name", "") or ""),
        summary=str(getattr(record, "source_summary", "") or ""),
        now=now,
    )


def active_for_review(record, *, now: datetime | None = None) -> bool:
    return classify_record(record, now=now).active
