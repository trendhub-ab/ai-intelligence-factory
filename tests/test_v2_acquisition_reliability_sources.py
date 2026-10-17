from __future__ import annotations

import pytest

import v2_github_live as github_live
import v2_official_vendor_live as vendor_live


class VendorResponse:
    def __init__(self, *, url: str, status_code: int = 200, text: str = ""):
        self.url = url
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: SECRET_VENDOR_BODY")


class GitHubResponse:
    def __init__(self, *, url: str, status_code: int = 200, payload=None):
        self.url = url
        self.status_code = status_code
        self._payload = [] if payload is None else payload
        self.text = "SECRET_GITHUB_BODY"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: SECRET_GITHUB_BODY")

    def json(self):
        return self._payload


RELEASE = {
    "id": 123,
    "html_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
    "name": "OpenAI Python v2.0.0",
    "tag_name": "v2.0.0",
    "body": "AI SDK release adds deployment and API improvements.",
    "published_at": "2026-10-15T20:00:00Z",
}


def test_official_vendor_503_retries_same_logical_read_once_then_recovers():
    source = vendor_live.OFFICIAL_VENDOR_SOURCES[0]
    calls = []

    def http_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return VendorResponse(url=url, status_code=503)
        return VendorResponse(
            url=url,
            text='<html><body><a href="/index/reliable-ai"><h2>Reliable AI API release</h2></a></body></html>',
        )

    rows = vendor_live.fetch_official_vendor_source(
        source=source,
        http_get=http_get,
        sleep_fn=lambda _seconds: None,
    )

    assert calls == [source.collection_url, source.collection_url]
    assert [row["title"] for row in rows] == ["Reliable AI API release"]


def test_official_vendor_400_is_not_retried_and_preserves_legacy_safe_category():
    source = vendor_live.OFFICIAL_VENDOR_SOURCES[0]
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return VendorResponse(url=url, status_code=400)

    with pytest.raises(vendor_live.VendorLiveError) as caught:
        vendor_live.fetch_official_vendor_source(
            source=source,
            http_get=http_get,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 1
    assert caught.value.category == "http_failure"
    assert "SECRET_VENDOR_BODY" not in str(caught.value)


def test_github_503_retries_same_repository_read_once_then_recovers():
    calls = []

    def http_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return GitHubResponse(url=url, status_code=503)
        return GitHubResponse(url=url, payload=[RELEASE])

    rows = github_live.fetch_github_repository_releases(
        repository="openai/openai-python",
        http_get=http_get,
        sleep_fn=lambda _seconds: None,
    )

    expected_url = "https://api.github.com/repos/openai/openai-python/releases"
    assert calls == [expected_url, expected_url]
    assert [row["upstream_id"] for row in rows] == ["123"]


def test_github_400_is_not_retried_and_preserves_legacy_safe_category():
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return GitHubResponse(url=url, status_code=400)

    with pytest.raises(github_live.GitHubLiveError) as caught:
        github_live.fetch_github_repository_releases(
            repository="openai/openai-python",
            http_get=http_get,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 1
    assert caught.value.category == "http_failure"
    assert "SECRET_GITHUB_BODY" not in str(caught.value)


def test_vendor_family_does_not_restart_after_one_logical_read_exhausts_retries():
    calls: dict[str, int] = {}

    def http_get(url, **kwargs):
        calls[url] = calls.get(url, 0) + 1
        if url == vendor_live.OFFICIAL_VENDOR_SOURCES[0].collection_url:
            return VendorResponse(url=url, status_code=503)
        return VendorResponse(url=url, text="<html><body></body></html>")

    rows = vendor_live.fetch_all_official_vendor_candidates(
        http_get=http_get,
        sleep_fn=lambda _seconds: None,
    )

    assert rows == []
    assert calls[vendor_live.OFFICIAL_VENDOR_SOURCES[0].collection_url] == 2
    assert calls[vendor_live.OFFICIAL_VENDOR_SOURCES[1].collection_url] == 1
    assert calls[vendor_live.OFFICIAL_VENDOR_SOURCES[2].collection_url] == 1


def test_github_family_does_not_restart_after_one_repository_exhausts_retries():
    calls: dict[str, int] = {}

    def http_get(url, **kwargs):
        calls[url] = calls.get(url, 0) + 1
        if "openai/openai-python" in url:
            return GitHubResponse(url=url, status_code=503)
        return GitHubResponse(url=url, payload=[])

    rows = github_live.fetch_all_github_candidates(
        http_get=http_get,
        sleep_fn=lambda _seconds: None,
    )

    assert rows == []
    assert calls["https://api.github.com/repos/openai/openai-python/releases"] == 2
    assert calls["https://api.github.com/repos/anthropics/anthropic-sdk-python/releases"] == 1
    assert calls["https://api.github.com/repos/googleapis/python-genai/releases"] == 1
