from __future__ import annotations

import importlib
import importlib.util

import pytest


def _live():
    spec = importlib.util.find_spec("v2_github_live")
    assert spec is not None, "v2_github_live must exist"
    return importlib.import_module("v2_github_live")


class _Response:
    def __init__(self, *, url: str, payload, status_code: int = 200):
        self.url = url
        self._payload = payload
        self.status_code = status_code
        self.text = "secret raw github body"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: secret raw github body")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


RELEASE = {
    "id": 123,
    "html_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
    "name": "OpenAI Python v2.0.0",
    "tag_name": "v2.0.0",
    "body": "AI SDK release adds deployment and API improvements.",
    "published_at": "2026-10-15T20:00:00Z",
}


def test_github_live_repositories_are_exact_and_ordered():
    live = _live()
    assert live.GITHUB_REPOSITORIES == (
        "openai/openai-python",
        "anthropics/anthropic-sdk-python",
        "googleapis/python-genai",
    )


def test_github_live_reads_releases_only_with_exact_budget():
    live = _live()
    calls = []

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(url=url, payload=[RELEASE])

    result = live.fetch_github_repository_releases(repository="openai/openai-python", http_get=http_get)
    assert calls == [(
        "https://api.github.com/repos/openai/openai-python/releases",
        {"params": {"per_page": 5}, "timeout": 8.0},
    )]
    assert result == [{
        "primary_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
        "title": "OpenAI Python v2.0.0",
        "description": "AI SDK release adds deployment and API improvements.",
        "published_at": "2026-10-15T20:00:00Z",
        "source_family": "github",
        "provider": "GitHub",
        "repository": "openai/openai-python",
        "event_kind": "release",
        "canonical_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
        "upstream_id": "123",
    }]


def test_github_live_rejects_unallowlisted_repository_before_network():
    live = _live()
    calls = []

    def http_get(url, **kwargs):
        calls.append(url)
        raise AssertionError("network must not be called")

    with pytest.raises(live.GitHubLiveError) as excinfo:
        live.fetch_github_repository_releases(repository="evil/not-approved", http_get=http_get)
    assert excinfo.value.category == "repository_unapproved"
    assert calls == []


def test_github_live_drops_malformed_release_rows():
    live = _live()
    malformed = [
        {"id": 1, "html_url": "https://evil.example/release", "name": "Bad host"},
        {"id": 2, "html_url": "https://github.com/openai/other/releases/tag/x", "name": "Wrong repo"},
        {"id": 3, "html_url": "https://github.com/openai/openai-python/releases/tag/x", "name": ""},
        RELEASE,
    ]

    def http_get(url, **kwargs):
        return _Response(url=url, payload=malformed)

    result = live.fetch_github_repository_releases(repository="openai/openai-python", http_get=http_get)
    assert [row["upstream_id"] for row in result] == ["123"]


def test_github_live_token_is_request_only_and_never_returned():
    live = _live()
    sentinel = "ghs_SUPER_SECRET_SENTINEL"
    seen_headers = []

    def http_get(url, **kwargs):
        seen_headers.append(kwargs.get("headers"))
        return _Response(url=url, payload=[RELEASE])

    result = live.fetch_github_repository_releases(
        repository="openai/openai-python", http_get=http_get, token=sentinel
    )
    assert seen_headers == [{"Authorization": f"Bearer {sentinel}"}]
    assert sentinel not in repr(result)


def test_github_live_rejects_redirect_escape_without_secret_leakage():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url="https://evil.example/releases", payload=[RELEASE])

    with pytest.raises(live.GitHubLiveError) as excinfo:
        live.fetch_github_repository_releases(
            repository="openai/openai-python", http_get=http_get, token="secret-token"
        )
    assert excinfo.value.category == "redirect_host_unapproved"
    assert "secret-token" not in str(excinfo.value)
    assert "secret raw github body" not in str(excinfo.value)


def test_github_live_invalid_json_has_safe_category():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, payload=ValueError("secret json detail"))

    with pytest.raises(live.GitHubLiveError) as excinfo:
        live.fetch_github_repository_releases(repository="openai/openai-python", http_get=http_get)
    assert excinfo.value.category == "invalid_json"
    assert "secret json detail" not in str(excinfo.value)


def test_github_live_one_repository_failure_is_isolated():
    live = _live()

    def http_get(url, **kwargs):
        if "openai/openai-python" in url:
            raise RuntimeError("secret first repo outage")
        repository = (
            "anthropics/anthropic-sdk-python"
            if "anthropics/anthropic-sdk-python" in url
            else "googleapis/python-genai"
        )
        owner, name = repository.split("/", 1)
        release = {
            "id": f"{owner}-{name}-1",
            "html_url": f"https://github.com/{repository}/releases/tag/v1.0.0",
            "name": f"{name} v1.0.0",
            "body": "AI SDK release improves deployment workflow.",
            "published_at": "2026-10-15T20:00:00Z",
        }
        return _Response(url=url, payload=[release])

    result = live.fetch_all_github_candidates(http_get=http_get)
    assert [row["repository"] for row in result] == [
        "anthropics/anthropic-sdk-python",
        "googleapis/python-genai",
    ]


def test_github_live_all_repository_failures_raise_family_failure():
    live = _live()

    def http_get(url, **kwargs):
        raise RuntimeError("secret github outage")

    with pytest.raises(live.GitHubLiveError) as excinfo:
        live.fetch_all_github_candidates(http_get=http_get)
    assert excinfo.value.repository == "GitHub"
    assert excinfo.value.category == "all_repositories_failed"
    assert "secret github outage" not in str(excinfo.value)


def test_github_live_successful_empty_repositories_are_not_failures():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, payload=[])

    assert live.fetch_all_github_candidates(http_get=http_get) == []
