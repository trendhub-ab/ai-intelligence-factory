from __future__ import annotations

import pytest
import requests

from v2_shadow_observation import GeminiEvidenceError, GeminiEvidenceProvider


CANDIDATE = {
    "candidate_identity": "https://example.com/item",
    "provider": "HackerNews",
    "primary_url": "https://example.com/item",
    "title": "Bounded AI evidence candidate",
    "description": "A bounded metadata record used only to test safe provider diagnostics.",
    "source_timestamp": "2026-10-14T00:00:00+00:00",
    "screening_score": 60,
    "screening_reasons": ["stable_identity", "description_substantive"],
}


class FakeResponse:
    def __init__(self, *, status_code: int = 200, json_data=None, json_error: Exception | None = None):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error
        self.text = "secret provider response body"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}: secret provider response body")

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


def _safe_code_for(http_post) -> str:
    provider = GeminiEvidenceProvider(api_key="test-key", http_post=http_post)
    with pytest.raises(GeminiEvidenceError) as excinfo:
        provider(CANDIDATE)
    assert "secret provider response body" not in str(excinfo.value)
    return excinfo.value.safe_code


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, "provider_http_400"),
        (401, "provider_http_401_403"),
        (403, "provider_http_401_403"),
        (404, "provider_http_404"),
        (429, "provider_http_429"),
        (500, "provider_http_5xx"),
        (503, "provider_http_5xx"),
    ],
)
def test_http_failures_are_classified_without_leaking_provider_body(status_code, expected):
    calls = 0

    def http_post(url, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(status_code=status_code)

    assert _safe_code_for(http_post) == expected
    assert calls == 1


def test_timeout_is_classified_without_retry():
    calls = 0

    def http_post(url, **kwargs):
        nonlocal calls
        calls += 1
        raise requests.Timeout("secret timeout detail")

    assert _safe_code_for(http_post) == "provider_timeout"
    assert calls == 1


def test_connection_error_is_classified_without_retry():
    calls = 0

    def http_post(url, **kwargs):
        nonlocal calls
        calls += 1
        raise requests.ConnectionError("secret connection detail")

    assert _safe_code_for(http_post) == "provider_connection_error"
    assert calls == 1


def test_successful_http_with_invalid_json_is_classified_separately():
    def http_post(url, **kwargs):
        return FakeResponse(status_code=200, json_error=ValueError("secret invalid json detail"))

    assert _safe_code_for(http_post) == "provider_response_json_invalid"
