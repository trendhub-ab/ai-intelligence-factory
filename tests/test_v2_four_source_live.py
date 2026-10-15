from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime, timezone
from unittest import mock


NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)


def _live():
    spec = importlib.util.find_spec("v2_four_source_live")
    assert spec is not None, "v2_four_source_live must exist"
    return importlib.import_module("v2_four_source_live")


def _candidate(family: str, suffix: str = "1") -> dict[str, str]:
    provider_host = {
        "official_vendor": "openai.com",
        "github": "github.com",
        "hacker_news": "example.com",
        "arxiv": "arxiv.org",
    }[family]
    return {
        "url": f"https://{provider_host}/{family}/{suffix}",
        "title": "AI API release improves enterprise deployment workflow",
        "description": "New AI release improves production workflow, cost, integration, and customer deployment.",
        "published_at": "2026-10-15T20:00:00+00:00",
        "source_family": family,
    }


def test_four_source_live_delegates_to_canonical_portfolio_with_exact_families():
    live = _live()
    captured = {}

    def fake_portfolio(**kwargs):
        captured.update(kwargs)
        rows = {name: provider() for name, provider in kwargs["providers"].items()}
        captured["rows"] = rows
        return {
            "run_id": kwargs["run_id"],
            "budgets": {"source_families": list(rows)},
            "actual_calls": {"provider": 4, "deep_dive": 0},
        }

    with mock.patch.object(live, "fetch_all_official_vendor_candidates", return_value=[_candidate("official_vendor")]), \
         mock.patch.object(live, "fetch_all_github_candidates", return_value=[_candidate("github")]), \
         mock.patch.object(live, "fetch_hacker_news_candidates", return_value=[_candidate("hacker_news")]), \
         mock.patch.object(live, "fetch_arxiv_candidates", return_value=[_candidate("arxiv")]), \
         mock.patch.object(live, "run_four_source_shadow", side_effect=fake_portfolio):
        report = live.run_four_source_live(
            deep_dive=lambda candidate: {"evidence_sufficient": True},
            now=NOW,
            run_id="four-source-contract",
        )

    assert list(captured["providers"]) == [
        "official_vendor",
        "github",
        "hacker_news",
        "arxiv",
    ]
    assert captured["rows"]["official_vendor"][0]["source_family"] == "official_vendor"
    assert captured["rows"]["github"][0]["source_family"] == "github"
    assert captured["rows"]["hacker_news"][0]["source_family"] == "hacker_news"
    assert captured["rows"]["arxiv"][0]["source_family"] == "arxiv"
    assert report["actual_calls"]["provider"] == 4


def test_four_source_live_adds_provenance_to_legacy_hn_arxiv_rows():
    live = _live()
    captured = {}

    def fake_portfolio(**kwargs):
        captured["hn"] = kwargs["providers"]["hacker_news"]()
        captured["arxiv"] = kwargs["providers"]["arxiv"]()
        return {"budgets": {}, "actual_calls": {"provider": 4, "deep_dive": 0}}

    hn = dict(_candidate("hacker_news"))
    hn.pop("source_family")
    arxiv = dict(_candidate("arxiv"))
    arxiv.pop("source_family")
    with mock.patch.object(live, "fetch_all_official_vendor_candidates", return_value=[]), \
         mock.patch.object(live, "fetch_all_github_candidates", return_value=[]), \
         mock.patch.object(live, "fetch_hacker_news_candidates", return_value=[hn]), \
         mock.patch.object(live, "fetch_arxiv_candidates", return_value=[arxiv]), \
         mock.patch.object(live, "run_four_source_shadow", side_effect=fake_portfolio):
        live.run_four_source_live(
            deep_dive=lambda candidate: {"evidence_sufficient": True},
            now=NOW,
            run_id="provenance",
        )

    assert captured["hn"][0]["source_family"] == "hacker_news"
    assert captured["arxiv"][0]["source_family"] == "arxiv"


def test_four_source_live_real_portfolio_isolates_source_failure_and_uses_one_deep_dive():
    live = _live()
    deep_dive_calls = []

    def fail_vendor(**kwargs):
        raise RuntimeError("secret vendor outage")

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": False}

    with mock.patch.object(live, "fetch_all_official_vendor_candidates", side_effect=fail_vendor), \
         mock.patch.object(live, "fetch_all_github_candidates", return_value=[_candidate("github")]), \
         mock.patch.object(live, "fetch_hacker_news_candidates", return_value=[_candidate("hacker_news")]), \
         mock.patch.object(live, "fetch_arxiv_candidates", return_value=[_candidate("arxiv")]):
        report = live.run_four_source_live(
            deep_dive=deep_dive,
            now=NOW,
            run_id="failure-isolation",
        )

    assert report["provider_statuses"]["OfficialVendor"]["status"] == "failure"
    assert report["provider_statuses"]["GitHub"]["normalized_count"] == 1
    assert report["provider_statuses"]["HackerNews"]["normalized_count"] == 1
    assert report["provider_statuses"]["ArXiv"]["normalized_count"] == 1
    assert report["actual_calls"]["provider"] == 4
    assert report["actual_calls"]["deep_dive"] == 1
    assert len(deep_dive_calls) == 1
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["v2_selected_candidate_identity"] is None


def test_four_source_live_honors_total_candidate_budget():
    live = _live()
    rows = [_candidate("official_vendor", str(index)) for index in range(1, 6)]
    with mock.patch.object(live, "fetch_all_official_vendor_candidates", return_value=rows), \
         mock.patch.object(live, "fetch_all_github_candidates", return_value=[_candidate("github")]), \
         mock.patch.object(live, "fetch_hacker_news_candidates", return_value=[_candidate("hacker_news")]), \
         mock.patch.object(live, "fetch_arxiv_candidates", return_value=[_candidate("arxiv")]):
        report = live.run_four_source_live(
            deep_dive=lambda candidate: {"evidence_sufficient": True},
            now=NOW,
            run_id="budget",
            config=live.FourSourceLiveConfig(max_total_candidates=2),
        )

    assert report["budgets"]["max_total_candidates"] == 2
    assert report["acquired_candidate_count"] == 2
    assert report["normalized_candidate_count"] == 2
    assert report["actual_calls"]["deep_dive"] <= 1


def test_four_source_live_never_rescues_rank2_after_rank1_provider_failure():
    live = _live()
    calls = []
    with mock.patch.object(live, "fetch_all_official_vendor_candidates", return_value=[_candidate("official_vendor", "1")]), \
         mock.patch.object(live, "fetch_all_github_candidates", return_value=[_candidate("github", "1")]), \
         mock.patch.object(live, "fetch_hacker_news_candidates", return_value=[]), \
         mock.patch.object(live, "fetch_arxiv_candidates", return_value=[]):
        def failing_deep_dive(candidate):
            calls.append(candidate["candidate_identity"])
            raise RuntimeError("provider failure")

        report = live.run_four_source_live(
            deep_dive=failing_deep_dive,
            now=NOW,
            run_id="no-rank2-rescue",
        )

    assert len(calls) == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["v2_selected_candidate_identity"] is None
