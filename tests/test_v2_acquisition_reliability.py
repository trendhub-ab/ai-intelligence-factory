from __future__ import annotations

import requests
import pytest

from v2_live_shadow_acquisition import AcquisitionRequestError, bounded_get


class FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.text = "SECRET_RESPONSE_BODY"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: SECRET_RESPONSE_BODY")


def test_timeout_retries_once_then_success_records_safe_diagnostics():
    calls = 0
    sleeps = []

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.Timeout("SECRET_TIMEOUT_DETAIL")
        return FakeResponse(200)

    response, diagnostics = bounded_get(
        http_get=http_get,
        url="https://example.test/feed",
        timeout=3.0,
        sleep_fn=sleeps.append,
        retry_delay_seconds=0.25,
    )

    assert response.status_code == 200
    assert calls == 2
    assert sleeps == [0.25]
    assert diagnostics.attempt_count == 2
    assert diagnostics.retry_used is True
    assert diagnostics.first_failure_category == "timeout"
    assert diagnostics.final_failure_category is None
    assert "SECRET" not in repr(diagnostics)


def test_http_429_and_503_are_retryable_but_400_is_not():
    for status_code in (429, 503):
        calls = []

        def retrying_get(url, **kwargs):
            calls.append(status_code)
            return FakeResponse(status_code if len(calls) == 1 else 200)

        response, diagnostics = bounded_get(
            http_get=retrying_get,
            url="https://example.test/feed",
            timeout=3.0,
            sleep_fn=lambda _seconds: None,
        )
        assert response.status_code == 200
        assert len(calls) == 2
        assert diagnostics.retry_used is True
        assert diagnostics.first_failure_category == ("http_429" if status_code == 429 else "http_5xx")

    calls_400 = 0

    def client_error_get(url, **kwargs):
        nonlocal calls_400
        calls_400 += 1
        return FakeResponse(400)

    with pytest.raises(AcquisitionRequestError) as caught:
        bounded_get(
            http_get=client_error_get,
            url="https://example.test/feed",
            timeout=3.0,
            sleep_fn=lambda _seconds: None,
        )

    assert calls_400 == 1
    assert caught.value.category == "http_4xx"
    assert caught.value.diagnostics.attempt_count == 1
    assert caught.value.diagnostics.retry_used is False


def test_connection_failure_stops_after_two_attempts_and_never_leaks_exception_text():
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        raise requests.ConnectionError("SECRET_CONNECTION_DETAIL")

    with pytest.raises(AcquisitionRequestError) as caught:
        bounded_get(
            http_get=http_get,
            url="https://example.test/feed",
            timeout=3.0,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 2
    assert caught.value.category == "connection"
    assert caught.value.diagnostics.attempt_count == 2
    assert caught.value.diagnostics.retry_used is True
    assert caught.value.diagnostics.first_failure_category == "connection"
    assert caught.value.diagnostics.final_failure_category == "connection"
    assert "SECRET_CONNECTION_DETAIL" not in str(caught.value)
    assert "SECRET_CONNECTION_DETAIL" not in repr(caught.value.diagnostics)


def test_retryable_first_failure_then_permanent_second_failure_stops_at_attempt_two():
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(503 if calls == 1 else 400)

    with pytest.raises(AcquisitionRequestError) as caught:
        bounded_get(
            http_get=http_get,
            url="https://example.test/feed",
            timeout=3.0,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 2
    assert caught.value.category == "http_4xx"
    assert caught.value.diagnostics.first_failure_category == "http_5xx"
    assert caught.value.diagnostics.final_failure_category == "http_4xx"


def test_unknown_request_exception_is_safe_non_retryable_request_failure():
    calls = 0

    def http_get(url, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("SECRET_UNKNOWN_TRANSPORT_DETAIL")

    with pytest.raises(AcquisitionRequestError) as caught:
        bounded_get(
            http_get=http_get,
            url="https://example.test/feed",
            timeout=3.0,
            sleep_fn=lambda _seconds: None,
        )

    assert calls == 1
    assert caught.value.category == "request_failure"
    assert caught.value.diagnostics.attempt_count == 1
    assert caught.value.diagnostics.retry_used is False
    assert "SECRET_UNKNOWN_TRANSPORT_DETAIL" not in str(caught.value)
