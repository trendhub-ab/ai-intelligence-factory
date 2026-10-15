"""Canonical four-source live acquisition bridge for V2-005C shadow proof.

The bridge composes the reviewed OfficialVendor/GitHub live readers with the
existing Hacker News/arXiv readers and delegates all portfolio budgeting,
selection, ranking, and one-shot Evidence authority to ``run_four_source_shadow``.
It performs no Production mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Mapping

import requests

from v2_github_live import fetch_all_github_candidates
from v2_live_shadow_acquisition import fetch_arxiv_candidates, fetch_hacker_news_candidates
from v2_official_vendor_live import fetch_all_official_vendor_candidates
from v2_shadow_selection import ShadowConfig
from v2_source_portfolio import SourcePortfolioConfig, run_four_source_shadow


@dataclass(frozen=True)
class FourSourceLiveConfig:
    vendor_limit: int = 5
    github_limit: int = 5
    hn_limit: int = 5
    arxiv_limit: int = 5
    timeout_seconds: float = 8.0
    max_total_candidates: int = 40

    def bounded(self) -> "FourSourceLiveConfig":
        return replace(
            self,
            vendor_limit=_bounded_int(self.vendor_limit, maximum=5),
            github_limit=_bounded_int(self.github_limit, maximum=5),
            hn_limit=_bounded_int(self.hn_limit, maximum=8),
            arxiv_limit=_bounded_int(self.arxiv_limit, maximum=8),
            timeout_seconds=_bounded_timeout(self.timeout_seconds),
            max_total_candidates=_bounded_int(self.max_total_candidates, maximum=40),
        )


def _bounded_int(value: Any, *, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(number, maximum))


def _bounded_timeout(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.1
    if number != number:
        return 0.1
    return max(0.1, min(number, 8.0))


def _with_source_family(rows: list[dict[str, Any]], source_family: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        enriched["source_family"] = source_family
        result.append(enriched)
    return result


def run_four_source_live(
    *,
    deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    now: datetime,
    run_id: str,
    http_get: Callable[..., Any] = requests.get,
    github_token: str | None = None,
    v1_reference: str | None = None,
    config: FourSourceLiveConfig | None = None,
) -> dict[str, Any]:
    """Acquire the exact four approved source families and run canonical shadow selection."""

    bounded = (config or FourSourceLiveConfig()).bounded()

    def vendor_provider() -> list[dict[str, Any]]:
        rows = fetch_all_official_vendor_candidates(http_get=http_get)
        return _with_source_family(rows[: bounded.vendor_limit], "official_vendor")

    def github_provider() -> list[dict[str, Any]]:
        rows = fetch_all_github_candidates(http_get=http_get, token=github_token)
        return _with_source_family(rows[: bounded.github_limit], "github")

    def hacker_news_provider() -> list[dict[str, Any]]:
        rows = fetch_hacker_news_candidates(
            http_get=http_get,
            limit=bounded.hn_limit,
            timeout_seconds=bounded.timeout_seconds,
        )
        return _with_source_family(rows, "hacker_news")

    def arxiv_provider() -> list[dict[str, Any]]:
        rows = fetch_arxiv_candidates(
            http_get=http_get,
            limit=bounded.arxiv_limit,
            timeout_seconds=bounded.timeout_seconds,
        )
        return _with_source_family(rows, "arxiv")

    max_per_provider = max(
        bounded.vendor_limit,
        bounded.github_limit,
        bounded.hn_limit,
        bounded.arxiv_limit,
        0,
    )
    report = run_four_source_shadow(
        providers={
            "official_vendor": vendor_provider,
            "github": github_provider,
            "hacker_news": hacker_news_provider,
            "arxiv": arxiv_provider,
        },
        deep_dive=deep_dive,
        shadow_config=ShadowConfig(
            max_candidates_per_provider=max_per_provider,
            max_deep_dive_attempts=1,
        ),
        portfolio_config=SourcePortfolioConfig(
            max_total_candidates=bounded.max_total_candidates,
        ),
        now=now,
        run_id=run_id,
        v1_reference=v1_reference,
    )
    report["live_acquisition"] = {
        "source_families": ["official_vendor", "github", "hacker_news", "arxiv"],
        "http_method": "GET",
        "vendor_limit": bounded.vendor_limit,
        "github_limit": bounded.github_limit,
        "hn_limit": bounded.hn_limit,
        "arxiv_limit": bounded.arxiv_limit,
        "timeout_seconds": bounded.timeout_seconds,
        "max_total_candidates": bounded.max_total_candidates,
    }
    return report
