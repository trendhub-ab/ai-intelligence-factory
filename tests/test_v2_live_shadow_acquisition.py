from __future__ import annotations

from datetime import datetime, timezone

import pytest

from v2_live_shadow_acquisition import (
    MAX_ARXIV_ITEMS,
    MAX_HN_ITEMS,
    MAX_TIMEOUT_SECONDS,
    MAX_TOTAL_CANDIDATES,
    LiveAcquisitionConfig,
    SourceAcquisitionError,
    fetch_arxiv_candidates,
    fetch_hacker_news_candidates,
    run_bounded_live_shadow,
)


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_config_is_clamped_to_safe_maxima():
    bounded = LiveAcquisitionConfig(
        hn_limit=999,
        arxiv_limit=999,
        total_candidate_limit=999,
        timeout_seconds=999,
    ).bounded()

    assert bounded.hn_limit == MAX_HN_ITEMS
    assert bounded.arxiv_limit == MAX_ARXIV_ITEMS
    assert bounded.total_candidate_limit == MAX_TOTAL_CANDIDATES
    assert bounded.timeout_seconds == MAX_TIMEOUT_SECONDS


def test_config_clamps_negative_limits_to_zero_and_timeout_to_positive_floor():
    bounded = LiveAcquisitionConfig(
        hn_limit=-1,
        arxiv_limit=-2,
        total_candidate_limit=-3,
        timeout_seconds=-4,
    ).bounded()

    assert bounded.hn_limit == 0
    assert bounded.arxiv_limit == 0
    assert bounded.total_candidate_limit == 0
    assert bounded.timeout_seconds > 0


def test_hn_maps_only_live_external_stories_and_keeps_bound():
    calls = []
    items = {
        1: {"id": 1, "type": "story", "title": "Alpha", "url": "https://alpha.example/a", "time": 1791930000, "score": 100, "descendants": 20},
        2: {"id": 2, "type": "story", "title": "No URL", "time": 1791930000},
        3: {"id": 3, "type": "comment", "title": "Comment", "url": "https://bad.example/c", "time": 1791930000},
        4: {"id": 4, "type": "story", "title": "Dead", "url": "https://bad.example/d", "dead": True, "time": 1791930000},
        5: {"id": 5, "type": "story", "title": "Beta", "url": "https://beta.example/b", "time": 1791930100, "score": 80, "descendants": 10},
    }

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[1, 2, 3, 4, 5, 6])
        item_id = int(url.rsplit("/", 1)[-1].split(".", 1)[0])
        return FakeResponse(json_data=items.get(item_id, {}))

    rows = fetch_hacker_news_candidates(http_get=http_get, limit=5, timeout_seconds=3)

    assert [row["title"] for row in rows] == ["Alpha", "Beta"]
    assert rows[0]["url"] == "https://alpha.example/a"
    assert rows[0]["published_at"].endswith("+00:00")
    assert "score=100" in rows[0]["description"]
    assert len(calls) == 6  # one list GET + five bounded item GETs
    assert all(call_kwargs["timeout"] == 3 for _, call_kwargs in calls)


def test_hn_item_failure_is_isolated_and_other_items_survive():
    def http_get(url, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[1, 2])
        if "/1.json" in url:
            raise TimeoutError("private transport detail")
        return FakeResponse(json_data={
            "id": 2,
            "type": "story",
            "title": "Survivor",
            "url": "https://survivor.example/story",
            "time": 1791930000,
        })

    rows = fetch_hacker_news_candidates(http_get=http_get, limit=2, timeout_seconds=2)
    assert [row["title"] for row in rows] == ["Survivor"]


def test_hn_top_list_failure_is_source_failure():
    def http_get(url, **kwargs):
        raise TimeoutError("secret network detail")

    with pytest.raises(SourceAcquisitionError):
        fetch_hacker_news_candidates(http_get=http_get, limit=2, timeout_seconds=2)


def _arxiv_xml(entries: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      {entries}
    </feed>'''


def test_arxiv_maps_atom_entries_and_keeps_abstract():
    xml = _arxiv_xml('''
      <entry>
        <id>https://arxiv.org/abs/2610.00001v1</id>
        <updated>2026-10-13T11:00:00Z</updated>
        <published>2026-10-13T10:00:00Z</published>
        <title>  Alpha   Paper  </title>
        <summary> A useful abstract about a new AI method. </summary>
      </entry>
      <entry>
        <id>https://arxiv.org/abs/2610.00002v1</id>
        <published>2026-10-13T09:00:00Z</published>
        <title>Beta Paper</title>
        <summary>Second abstract.</summary>
      </entry>
    ''')
    seen = []

    def http_get(url, **kwargs):
        seen.append((url, kwargs))
        return FakeResponse(text=xml)

    rows = fetch_arxiv_candidates(http_get=http_get, limit=2, timeout_seconds=4)

    assert len(rows) == 2
    assert rows[0] == {
        "url": "https://arxiv.org/abs/2610.00001v1",
        "title": "Alpha Paper",
        "description": "A useful abstract about a new AI method.",
        "published_at": "2026-10-13T10:00:00Z",
    }
    assert seen[0][0] == "https://export.arxiv.org/api/query"
    assert seen[0][1]["params"]["search_query"] == "cat:cs.AI OR cat:cs.LG"
    assert seen[0][1]["params"]["max_results"] == 2
    assert seen[0][1]["timeout"] == 4


def test_arxiv_malformed_xml_fails_closed():
    def http_get(url, **kwargs):
        return FakeResponse(text="<feed><broken>")

    with pytest.raises(SourceAcquisitionError):
        fetch_arxiv_candidates(http_get=http_get, limit=2, timeout_seconds=2)


def test_bounded_live_shadow_isolates_arxiv_failure_and_hn_can_win():
    def http_get(url, **kwargs):
        if "hacker-news" in url and url.endswith("topstories.json"):
            return FakeResponse(json_data=[101])
        if "hacker-news" in url and "/101.json" in url:
            return FakeResponse(json_data={
                "id": 101,
                "type": "story",
                "title": "Current AI release",
                "url": "https://vendor.example/releases/current",
                "time": 1791930000,
                "score": 150,
                "descendants": 50,
            })
        if "export.arxiv.org" in url:
            raise TimeoutError("do not leak this text")
        raise AssertionError(url)

    deep_dive_calls = []

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_bounded_live_shadow(
        http_get=http_get,
        deep_dive=deep_dive,
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=2, total_candidate_limit=3),
        now=NOW,
        run_id="v2-002-test",
        v1_reference=None,
    )

    assert report["mode"] == "shadow"
    assert report["provider_statuses"]["HackerNews"]["status"] == "success"
    assert report["provider_statuses"]["ArXiv"]["status"] == "failure"
    assert report["deep_dive_attempted_count"] == 1
    assert len(deep_dive_calls) == 1
    assert report["v2_selected_candidate_identity"] == "https://vendor.example/releases/current"
    assert report["comparison_status"] == "unavailable"
    assert report["live_acquisition"]["total_candidate_limit"] == 3
    assert "do not leak this text" not in str(report)


def test_bounded_live_shadow_enforces_combined_candidate_limit_before_selection():
    hn_ids = list(range(1, 9))

    def http_get(url, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=hn_ids)
        if "hacker-news" in url:
            item_id = int(url.rsplit("/", 1)[-1].split(".", 1)[0])
            return FakeResponse(json_data={
                "id": item_id,
                "type": "story",
                "title": f"HN {item_id}",
                "url": f"https://hn.example/{item_id}",
                "time": 1791930000,
            })
        if "export.arxiv.org" in url:
            entries = "".join(
                f'''<entry><id>https://arxiv.org/abs/2610.{i:05d}v1</id><published>2026-10-13T10:00:00Z</published><title>Paper {i}</title><summary>Long enough abstract for candidate {i} to be screened successfully by the V2 core.</summary></entry>'''
                for i in range(1, 9)
            )
            return FakeResponse(text=_arxiv_xml(entries))
        raise AssertionError(url)

    report = run_bounded_live_shadow(
        http_get=http_get,
        deep_dive=lambda candidate: {"evidence_sufficient": False},
        config=LiveAcquisitionConfig(hn_limit=8, arxiv_limit=8, total_candidate_limit=5),
        now=NOW,
        run_id="bounded-total",
    )

    assert report["acquired_candidate_count"] <= 5
    assert report["normalized_candidate_count"] <= 5
    assert report["live_acquisition"]["total_candidate_limit"] == 5
    assert report["deep_dive_attempted_count"] <= 1


def test_both_sources_failure_returns_no_winner_without_raising():
    def http_get(url, **kwargs):
        raise TimeoutError("opaque source failure")

    report = run_bounded_live_shadow(
        http_get=http_get,
        deep_dive=lambda candidate: pytest.fail("Deep Dive must not run"),
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1),
        now=NOW,
        run_id="all-down",
    )

    assert report["failure_category"] == "all_providers_failed"
    assert report["v2_selected_candidate_identity"] is None
    assert report["deep_dive_attempted_count"] == 0
    assert report["provider_statuses"]["HackerNews"]["status"] == "failure"
    assert report["provider_statuses"]["ArXiv"]["status"] == "failure"
