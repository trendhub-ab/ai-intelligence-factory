"""Shared bounded GET reliability contract for AIIF V2 shadow acquisition.

This module owns only safe transport/HTTP classification and one bounded retry.
It has no Production authority, persistence hooks, model calls, or source parsing.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Mapping

import requests


_RETRYABLE_CATEGORIES = frozenset({"timeout", "connection", "http_429", "http_5xx"})
MAX_RETRY_DELAY_SECONDS = 3.0


@dataclass(frozen=True)
class AcquisitionDiagnostics:
    attempt_count: int
    retry_used: bool
    first_failure_category: str | None
    final_failure_category: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "attempt_count": self.attempt_count,
            "retry_used": self.retry_used,
            "first_failure_category": self.first_failure_category,
            "final_failure_category": self.final_failure_category,
        }


class AcquisitionRequestError(RuntimeError):
    """Opaque bounded acquisition failure safe for diagnostic artifacts."""

    def __init__(self, category: str, diagnostics: AcquisitionDiagnostics) -> None:
        self.category = str(category)
        self.diagnostics = diagnostics
        super().__init__(self.category)


def _transport_category(exc: BaseException) -> str:
    if isinstance(exc, (requests.Timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, (requests.ConnectionError, ConnectionError)):
        return "connection"
    return "request_failure"


def _status_category(status_code: int) -> str:
    if status_code == 429:
        return "http_429"
    if 500 <= status_code <= 599:
        return "http_5xx"
    if 400 <= status_code <= 499:
        return "http_4xx"
    return "request_failure"


def _bounded_delay(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if number != number:
        return 0.0
    return max(0.0, min(number, MAX_RETRY_DELAY_SECONDS))


def _diagnostics(
    *,
    attempt_count: int,
    first_failure_category: str | None,
    final_failure_category: str | None,
) -> AcquisitionDiagnostics:
    return AcquisitionDiagnostics(
        attempt_count=attempt_count,
        retry_used=attempt_count > 1,
        first_failure_category=first_failure_category,
        final_failure_category=final_failure_category,
    )


def bounded_get(
    *,
    http_get: Callable[..., Any],
    url: str,
    timeout: float,
    request_kwargs: Mapping[str, Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    retry_delay_seconds: float = 0.25,
) -> tuple[Any, AcquisitionDiagnostics]:
    """Perform one logical GET with at most one retry for transient failures."""

    kwargs = dict(request_kwargs or {})
    kwargs.pop("timeout", None)
    delay = _bounded_delay(retry_delay_seconds)
    first_failure: str | None = None

    for attempt in (1, 2):
        try:
            response = http_get(url, timeout=timeout, **kwargs)
        except Exception as exc:
            category = _transport_category(exc)
        else:
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and status_code >= 400:
                category = _status_category(status_code)
            else:
                try:
                    raise_for_status = getattr(response, "raise_for_status", None)
                    if callable(raise_for_status):
                        raise_for_status()
                except Exception:
                    category = "request_failure"
                else:
                    return response, _diagnostics(
                        attempt_count=attempt,
                        first_failure_category=first_failure,
                        final_failure_category=None,
                    )

        if first_failure is None:
            first_failure = category
        if category in _RETRYABLE_CATEGORIES and attempt == 1:
            sleep_fn(delay)
            continue

        raise AcquisitionRequestError(
            category,
            _diagnostics(
                attempt_count=attempt,
                first_failure_category=first_failure,
                final_failure_category=category,
            ),
        ) from None

    raise AssertionError("bounded acquisition loop exhausted unexpectedly")
