"""AIIF Rebuild V2-002 bounded live shadow acquisition.

This module adds read-only public acquisition to the V2-001 shadow selector.
It deliberately does not import pipeline.py or any Production persistence,
publication, Notion, note, queue, Ready-state, or model-provider surface.

Network access is GET-only and injectable. The only default network dependency
is requests.get. Deep Dive remains an injected callback owned by V2-001 and is
therefore still bounded to at most one attempt per run.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping
import xml.etree.ElementTree as ET

import requests

from v2_shadow_selection import ShadowConfig, run_shadow_selection


HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_SEARCH_QUERY = "cat:cs.AI OR cat:cs.LG"

MAX_HN_ITEMS = 8
MAX_ARXIV_ITEMS = 8
MAX_TOTAL_CANDIDATES = 12
MAX_TIMEOUT_SECONDS = 8.0
MIN_TIMEOUT_SECONDS = 0.1
MAX_RETRY_DELAY_SECONDS = 3.0
_RETRYABLE_CATEGORIES = frozenset({"timeout", "connection", "http_429", "http_5xx"})


@dataclass(frozen=True)
class AcquisitionDiagnostics:
    """Safe diagnostics for one bounded logical HTTP read."""

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
    """Opaque bounded transport/HTTP failure safe for diagnostics."""

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


def _bounded_retry_delay(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if number != number:
        return 0.0
    return max(0.0, min(number, MAX_RETRY_DELAY_SECONDS))


def _acquisition_diagnostics(
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
    delay = _bounded_retry_delay(retry_delay_seconds)
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
                    return response, _acquisition_diagnostics(
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
            _acquisition_diagnostics(
                attempt_count=attempt,
                first_failure_category=first_failure,
                final_failure_category=category,
            ),
        ) from None

    raise AssertionError("bounded acquisition loop exhausted unexpectedly")


class SourceAcquisitionError(RuntimeError):
    """Opaque source-boundary failure safe for structured shadow reporting."""

    def __init__(self, source: str, category: str):
        self.source = str(source)
        self.category = str(category)
        super().__init__(f"{self.source}:{self.category}")


@dataclass(frozen=True)
class LiveAcquisitionConfig:
    """Bounded configuration for manual V2-002 live shadow acquisition."""

    hn_limit: int = 5
    arxiv_limit: int = 5
    total_candidate_limit: int = 10
    timeout_seconds: float = 5.0

    def bounded(self) -> "LiveAcquisitionConfig":
        return replace(
            self,
            hn_limit=_bounded_int(self.hn_limit, maximum=MAX_HN_ITEMS),
            arxiv_limit=_bounded_int(self.arxiv_limit, maximum=MAX_ARXIV_ITEMS),
            total_candidate_limit=_bounded_int(
                self.total_candidate_limit,
                maximum=MAX_TOTAL_CANDIDATES,
            ),
            timeout_seconds=_bounded_timeout(self.timeout_seconds),
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
        return MIN_TIMEOUT_SECONDS
    if number != number:  # NaN
        return MIN_TIMEOUT_SECONDS
    return max(MIN_TIMEOUT_SECONDS, min(number, MAX_TIMEOUT_SECONDS))


def _bounded_deep_dive_attempts(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return 0 if number <= 0 else 1


def _check_response(response: Any, *, source: str) -> None:
    try:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
            return
        status = int(getattr(response, "status_code", 200) or 200)
        if status >= 400:
            raise RuntimeError("HTTP failure")
    except Exception as exc:
        raise SourceAcquisitionError(source, "http_failure") from exc


def _response_json(response: Any, *, source: str) -> Any:
    _check_response(response, source=source)
    try:
        return response.json()
    except Exception as exc:
        raise SourceAcquisitionError(source, "invalid_json") from exc


def _response_text(response: Any, *, source: str) -> str:
    _check_response(response, source=source)
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(response, "content", b"")
    try:
        return bytes(content).decode("utf-8")
    except Exception as exc:
        raise SourceAcquisitionError(source, "invalid_text") from exc


def _utc_iso_from_unix(value: Any) -> str | None:
    try:
        timestamp = int(value)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def fetch_hacker_news_candidates(
    *,
    http_get: Callable[..., Any] = requests.get,
    limit: int = 5,
    timeout_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    """Fetch bounded public Hacker News stories using GET only.

    Failure of the top-story list is a source-level failure. Failure of one
    individual item is isolated and that item is skipped.
    """

    bounded_limit = _bounded_int(limit, maximum=MAX_HN_ITEMS)
    timeout = _bounded_timeout(timeout_seconds)
    if bounded_limit == 0:
        return []

    try:
        top_response = http_get(HN_TOPSTORIES_URL, timeout=timeout)
        top_ids = _response_json(top_response, source="HackerNews")
    except SourceAcquisitionError:
        raise
    except Exception as exc:
        raise SourceAcquisitionError("HackerNews", "request_failure") from exc

    if not isinstance(top_ids, list):
        raise SourceAcquisitionError("HackerNews", "invalid_payload")

    candidates: list[dict[str, Any]] = []
    for raw_id in top_ids[:bounded_limit]:
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError, OverflowError):
            continue
        try:
            item_response = http_get(HN_ITEM_URL.format(item_id=item_id), timeout=timeout)
            item = _response_json(item_response, source="HackerNews")
        except Exception:
            continue
        if not isinstance(item, Mapping):
            continue
        if item.get("type") != "story" or item.get("deleted") is True or item.get("dead") is True:
            continue
        title = _clean_text(item.get("title"))
        url = _clean_text(item.get("url"))
        if not title or not url.startswith(("http://", "https://")):
            continue

        metadata: list[str] = []
        score = item.get("score")
        comments = item.get("descendants")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            metadata.append(f"score={int(score)}")
        if isinstance(comments, (int, float)) and not isinstance(comments, bool):
            metadata.append(f"comments={int(comments)}")

        candidate: dict[str, Any] = {
            "url": url,
            "title": title,
            "description": "HN " + "; ".join(metadata) if metadata else "Hacker News story",
        }
        published_at = _utc_iso_from_unix(item.get("time"))
        if published_at:
            candidate["published_at"] = published_at
        candidates.append(candidate)

    return candidates


def fetch_arxiv_candidates(
    *,
    http_get: Callable[..., Any] = requests.get,
    limit: int = 5,
    timeout_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    """Fetch bounded newest AI/ML arXiv metadata using GET only."""

    bounded_limit = _bounded_int(limit, maximum=MAX_ARXIV_ITEMS)
    timeout = _bounded_timeout(timeout_seconds)
    if bounded_limit == 0:
        return []

    params = {
        "search_query": ARXIV_SEARCH_QUERY,
        "start": 0,
        "max_results": bounded_limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        response = http_get(ARXIV_API_URL, params=params, timeout=timeout)
        xml_text = _response_text(response, source="ArXiv")
    except SourceAcquisitionError:
        raise
    except Exception as exc:
        raise SourceAcquisitionError("ArXiv", "request_failure") from exc

    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, TypeError, ValueError) as exc:
        raise SourceAcquisitionError("ArXiv", "invalid_xml") from exc

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    candidates: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns)[:bounded_limit]:
        entry_id = _clean_text(entry.findtext("atom:id", default="", namespaces=ns))
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        if not entry_id.startswith(("http://", "https://")) or not title:
            continue
        description = _clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        published = _clean_text(entry.findtext("atom:published", default="", namespaces=ns))
        if not published:
            published = _clean_text(entry.findtext("atom:updated", default="", namespaces=ns))

        candidate: dict[str, Any] = {
            "url": entry_id,
            "title": title,
            "description": description,
        }
        if published:
            candidate["published_at"] = published
        candidates.append(candidate)

    return candidates


def run_bounded_live_shadow(
    *,
    deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    now: datetime,
    run_id: str,
    config: LiveAcquisitionConfig | None = None,
    http_get: Callable[..., Any] = requests.get,
    v1_reference: str | None = None,
    max_deep_dive_attempts: int = 1,
) -> dict[str, Any]:
    """Acquire two public sources and feed them into V2-001 shadow selection.

    The shared remaining counter enforces the total candidate cap before raw
    candidates reach V2-001. Provider order is deterministic: Hacker News then
    arXiv. A failing provider does not consume the shared candidate budget.
    """

    bounded = (config or LiveAcquisitionConfig()).bounded()
    remaining = bounded.total_candidate_limit
    deep_dive_budget = _bounded_deep_dive_attempts(max_deep_dive_attempts)

    def bounded_hn_provider() -> list[dict[str, Any]]:
        nonlocal remaining
        if remaining <= 0 or bounded.hn_limit <= 0:
            return []
        rows = fetch_hacker_news_candidates(
            http_get=http_get,
            limit=min(bounded.hn_limit, remaining),
            timeout_seconds=bounded.timeout_seconds,
        )
        accepted = rows[:remaining]
        remaining -= len(accepted)
        return accepted

    def bounded_arxiv_provider() -> list[dict[str, Any]]:
        nonlocal remaining
        if remaining <= 0 or bounded.arxiv_limit <= 0:
            return []
        rows = fetch_arxiv_candidates(
            http_get=http_get,
            limit=min(bounded.arxiv_limit, remaining),
            timeout_seconds=bounded.timeout_seconds,
        )
        accepted = rows[:remaining]
        remaining -= len(accepted)
        return accepted

    report = run_shadow_selection(
        providers={
            "HackerNews": bounded_hn_provider,
            "ArXiv": bounded_arxiv_provider,
        },
        deep_dive=deep_dive,
        config=ShadowConfig(
            max_candidates_per_provider=bounded.total_candidate_limit,
            max_deep_dive_attempts=deep_dive_budget,
        ),
        now=now,
        run_id=run_id,
        v1_reference=v1_reference,
    )

    return {
        **report,
        "live_acquisition": {
            "sources": ["HackerNews", "ArXiv"],
            "http_method": "GET",
            "hn_limit": bounded.hn_limit,
            "arxiv_limit": bounded.arxiv_limit,
            "total_candidate_limit": bounded.total_candidate_limit,
            "timeout_seconds": bounded.timeout_seconds,
        },
    }
