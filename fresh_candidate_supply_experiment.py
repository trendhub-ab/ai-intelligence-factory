"""Opt-in zero-Gemini *candidate-supply* experiment, never normal Fresh.

The experiment changes only GitHub discovery breadth, not quality policy.
Its baseline plus two extra topic queries are deliberately interleaved BEFORE
the unchanged 50-item per-source cap. Otherwise a saturated baseline would
consume all 50 slots and make alternative queries pointless.

The result is a proposed new sample/protocol. It cannot be compared to the
historical 1/4 source-stratified campaign or counted as a Fresh PASS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable

PROTOCOL_ID = "source-supply-gh-3-cohorts-v1"
GITHUB_COHORTS = (
    ("baseline", "topic:ai topic:machine-learning"),
    ("generative_ai", "topic:generative-ai"),
    ("large_language_model", "topic:large-language-model"),
)
MAX_GITHUB_QUERY_CALLS = 3
PER_QUERY_MAX = 50
GITHUB_PRESENTED_MAX = 50


def queries(*, now: datetime) -> list[tuple[str, str]]:
    """Deterministic clock injection: prevent the cohort window drifting mid-run."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Supply experiment requires a timezone-aware UTC clock")
    since = (now.astimezone(timezone.utc) - timedelta(days=30)).date().isoformat()
    return [
        (label, f"{topic} stars:>100 pushed:>{since}")
        for label, topic in GITHUB_COHORTS
    ]


def interleave_unique(
    cohorts: list[tuple[str, list[dict]]], *, identity: Callable[[dict], set[str]], cap: int
) -> tuple[list[dict], dict[str, dict[str, int]]]:
    """One deterministic item per cohort per round; no global rank or score change."""
    if not 0 <= cap <= GITHUB_PRESENTED_MAX or len(cohorts) != MAX_GITHUB_QUERY_CALLS:
        raise RuntimeError("Supply experiment bounds have changed")
    if tuple(label for label, _ in cohorts) != tuple(c[0] for c in GITHUB_COHORTS):
        raise RuntimeError("Supply experiment cohort ordering changed")
    chosen: list[dict] = []
    seen: set[str] = set()
    metrics = {
        label: {"raw": len(rows), "unique_presented": 0, "intra_cohort_deduped": 0}
        for label, rows in cohorts
    }
    for rownum in range(max((len(rows) for _, rows in cohorts), default=0)):
        for label, rows in cohorts:
            if len(chosen) >= cap:
                return chosen, metrics
            if rownum >= len(rows):
                continue
            row = rows[rownum]
            urls = identity(row)
            if not urls:
                # Existing legal/source/identity gates decide whether URL-less
                # data is usable. Never claim that a missing URL is unique.
                metrics[label]["intra_cohort_deduped"] += 1
                continue
            if seen.intersection(urls):
                metrics[label]["intra_cohort_deduped"] += 1
                continue
            chosen.append(row)
            seen.update(urls)
            metrics[label]["unique_presented"] += 1
    return chosen, metrics


def make_fetcher(
    pipeline: Any,
    *,
    capture: dict,
    fetch_page: Callable[[str, int], list[dict]] | None = None,
    now: datetime | None = None,
):
    """Return opt-in GitHub fetch callable; no API request occurs on construction."""
    if fetch_page is None:
        def fetch_page(query: str, first: int) -> list[dict]:
            # Match the original Production GraphQL fields exactly.
            gql = (
                "{ search(query: " + json.dumps(query)
                + f", type: REPOSITORY, first: {first}) "
                + "{ nodes { ... on Repository { nameWithOwner url description "
                + "stargazerCount pushedAt licenseInfo { spdxId } } } } }"
            )
            response = pipeline.requests.post(
                "https://api.github.com/graphql",
                json={"query": gql},
                headers={"Authorization": f"Bearer {pipeline.GH_PAT}", "Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code != 200:
                raise RuntimeError("Source-supply GitHub query failed; no partial cohort")
            payload = response.json()
            if payload.get("errors") or not isinstance(payload.get("data", {}).get("search", {}).get("nodes"), list):
                raise RuntimeError("Source-supply GitHub GraphQL result invalid")
            return payload["data"]["search"]["nodes"]

    clock = now if now is not None else datetime.now(timezone.utc)
    frozen_queries = queries(now=clock)

    def fetch(limit: int) -> list[dict]:
        if not 0 <= limit <= GITHUB_PRESENTED_MAX:
            raise RuntimeError("Experimental GitHub presentation cap exceeded")
        normalized_cohorts = []
        for label, query in frozen_queries:
            raw = fetch_page(query, PER_QUERY_MAX)
            if not isinstance(raw, list) or len(raw) > PER_QUERY_MAX:
                raise RuntimeError("Invalid or unbounded supply experiment cohort")
            normalized = [
                pipeline.normalize_item(
                    source="GitHub",
                    name=row.get("nameWithOwner"),
                    url=row.get("url"),
                    description=row.get("description"),
                    engagement=row.get("stargazerCount", 0),
                    license_info=row.get("licenseInfo"),
                    published_at=row.get("pushedAt"),
                )
                for row in raw
                if isinstance(row, dict)
            ]
            normalized_cohorts.append((label, normalized))
        selected, metrics = interleave_unique(
            normalized_cohorts, identity=pipeline.candidate_identity_urls, cap=limit
        )
        capture.update({
            "protocol": PROTOCOL_ID,
            "github_graphql_queries": len(frozen_queries),
            "github_presented_limit": limit,
            "github_cohorts": metrics,
        })
        return selected

    return fetch
