"""Bounded four-source orchestration for AIIF V2 shadow selection.

V2 shadow only. This module composes OfficialVendor, GitHub, Hacker News, and
ArXiv provider callables into the existing V2 selection/Evidence path while
keeping a deterministic total acquisition budget. It performs no fetching,
model calls, persistence, or Production mutation itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from typing import Any

from v2_shadow_selection import ShadowConfig, run_shadow_selection


SOURCE_FAMILY_ORDER = (
    "official_vendor",
    "github",
    "hacker_news",
    "arxiv",
)
_SOURCE_PROVIDER_NAMES = {
    "official_vendor": "OfficialVendor",
    "github": "GitHub",
    "hacker_news": "HackerNews",
    "arxiv": "ArXiv",
}
DEFAULT_MAX_TOTAL_CANDIDATES = 40


@dataclass(frozen=True)
class SourcePortfolioConfig:
    """Explicit total acquisition budget for the four-source V2 shadow slice."""

    max_total_candidates: int = DEFAULT_MAX_TOTAL_CANDIDATES


def _validate_source_portfolio(
    providers: Mapping[str, Callable[[], Iterable[Mapping[str, Any]]]],
) -> None:
    actual = set(providers)
    expected = set(SOURCE_FAMILY_ORDER)
    if actual != expected:
        raise ValueError("four-source portfolio must contain exactly OfficialVendor, GitHub, Hacker News, and ArXiv")


def run_four_source_shadow(
    *,
    providers: Mapping[str, Callable[[], Iterable[Mapping[str, Any]]]],
    deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    shadow_config: ShadowConfig,
    portfolio_config: SourcePortfolioConfig,
    now: datetime,
    run_id: str,
    v1_reference: str | None = None,
) -> dict[str, Any]:
    """Run the exact four-source portfolio through the existing shadow path.

    Each source keeps the existing per-provider cap from ``ShadowConfig``. A
    separate shared total budget bounds the combined portfolio. Provider order
    is fixed by ``SOURCE_FAMILY_ORDER`` so allocation is deterministic. If one
    provider raises before returning items, it consumes no total candidate
    budget and the remaining providers still run. The wrapped call delegates
    ranking and the single Evidence attempt to ``run_shadow_selection``.
    """

    _validate_source_portfolio(providers)

    total_budget = int(portfolio_config.max_total_candidates)
    if total_budget < 0:
        raise ValueError("max_total_candidates must be non-negative")

    per_provider_budget = max(0, int(shadow_config.max_candidates_per_provider))
    remaining = {"count": total_budget}
    wrapped: dict[str, Callable[[], Iterable[Mapping[str, Any]]]] = {}

    for source_family in SOURCE_FAMILY_ORDER:
        provider = providers[source_family]
        provider_name = _SOURCE_PROVIDER_NAMES[source_family]

        def bounded_provider(
            provider: Callable[[], Iterable[Mapping[str, Any]]] = provider,
        ) -> list[Mapping[str, Any]]:
            raw_items = provider()
            limit = min(per_provider_budget, remaining["count"])
            if limit <= 0:
                return []
            bounded = list(islice(iter(raw_items), limit))
            remaining["count"] -= len(bounded)
            return bounded

        wrapped[provider_name] = bounded_provider

    report = run_shadow_selection(
        providers=wrapped,
        deep_dive=deep_dive,
        config=shadow_config,
        now=now,
        run_id=run_id,
        v1_reference=v1_reference,
    )
    report["budgets"]["max_total_candidates"] = total_budget
    report["budgets"]["source_families"] = list(SOURCE_FAMILY_ORDER)
    return report
