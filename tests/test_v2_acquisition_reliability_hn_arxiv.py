from __future__ import annotations

import requests
import pytest

import v2_live_shadow_acquisition as live


class FakeResponse:
    def __init__(self, *, status_code: int = 200, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: SECRET_BODY")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://arxiv.org/abs/2610.12345</id>
    <title>Reliable AI agents for bounded workflows</title>
    <summary>We study reliable AI agents for production workflow decisions.</summary>
    <published>2026-10-16T10:00:00Z</published>
  </entry>
</feed>
"""


def _hn_story(item_id: int = 1):
    return {
        "id": item_id,
        "type": "story",
        "title": "AI API reliability update",
        "url": "https://example.com/ai-api-reliability",
        "time": 1792123200,
        "score": 100,
        "descendants": 20,
    }


def test_hn_topstories_timeout_retries_once_then_recovers_without_repeating_after_success():
    top_calls = 0

    def http_get(url, **kwargs):
        nonlocal top_calls
        if url == live.HN_TOPSTORIES_URL:
            top_calls += 1
            if top_calls == 1:
                raise requests.Timeout("SECRET_TIMEOUT")
            return FakeResponse(payload=[1])
        return FakeResponse(payload=_hn_story(1))

    rows = live.fetch_hacker_news_candidates(
        http_get=http_get,
        limit=1,
        sleep_fn=lambda _seconds: None,
    )

    assert top_calls == 2
    assert len(rows) == 1


def test_hn_topstories_http_400_is_not_retried():
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(status_code=400, payload=[])

    with pytest.raises(live.SourceAcquisitionError) as caught:
        live.fetch_hacker_news_candidates(
            http_get=http_get,
            limit=1,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 1
    assert caught.value.category == "http_4xx"


def test_hn_item_failure_exhausts_two_attempts_then_next_item_survives_without_topstory_restart():
    counts: dict[str, int] = {}

    def http_get(url, **kwargs):
        counts[url] = counts.get(url, 0) + 1
        if url == live.HN_TOPSTORIES_URL:
            return FakeResponse(payload=[1, 2])
        if url.endswith("/1.json"):
            raise requests.ConnectionError("SECRET_ITEM_FAILURE")
        return FakeResponse(payload=_hn_story(2))

    rows = live.fetch_hacker_news_candidates(
        http_get=http_get,
        limit=2,
        sleep_fn=lambda _seconds: None,
    )

    assert counts[live.HN_TOPSTORIES_URL] == 1
    assert counts[live.HN_ITEM_URL.format(item_id=1)] == 2
    assert counts[live.HN_ITEM_URL.format(item_id=2)] == 1
    assert len(rows) == 1


def test_arxiv_http_503_retries_once_then_recovers():
    calls = 0
    sleeps = []

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(status_code=503, text="SECRET_503")
        return FakeResponse(text=ARXIV_XML)

    rows = live.fetch_arxiv_candidates(
        http_get=http_get,
        limit=1,
        sleep_fn=sleeps.append,
    )

    assert calls == 2
    assert sleeps == [3.0]
    assert len(rows) == 1


def test_arxiv_http_400_and_invalid_xml_are_not_retried():
    calls_400 = 0

    def bad_request(url, **kwargs):
        nonlocal calls_400
        calls_400 += 1
        return FakeResponse(status_code=400, text="bad")

    with pytest.raises(live.SourceAcquisitionError) as caught:
        live.fetch_arxiv_candidates(
            http_get=bad_request,
            limit=1,
            sleep_fn=lambda _seconds: None,
        )
    assert calls_400 == 1
    assert caught.value.category == "http_4xx"

    invalid_calls = 0

    def invalid_xml(url, **kwargs):
        nonlocal invalid_calls
        invalid_calls += 1
        return FakeResponse(text="<not-closed")

    with pytest.raises(live.SourceAcquisitionError) as caught_xml:
        live.fetch_arxiv_candidates(
            http_get=invalid_xml,
            limit=1,
            sleep_fn=lambda _seconds: None,
        )
    assert invalid_calls == 1
    assert caught_xml.value.category == "invalid_xml"
