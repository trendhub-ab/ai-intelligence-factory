"""Bounded GET-only GitHub releases reader for V2-005C shadow proof.

Only three reviewed repositories and their releases collections are read. The
module delegates normalization to the existing V2-005B GitHub adapter and has
no write, discovery, tag fallback, model, persistence, or Production authority.
"""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit

import requests

from v2_github_acquisition import acquire_github_candidates


GITHUB_REPOSITORIES: tuple[str, ...] = (
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "googleapis/python-genai",
)


class GitHubLiveError(RuntimeError):
    """Safe categorical GitHub live-read failure."""

    def __init__(self, repository: str, category: str) -> None:
        self.repository = str(repository)
        self.category = str(category)
        super().__init__(f"{self.repository}:{self.category}")


def _clean_text(value: object) -> str:
    return " ".join(value.split()).strip() if isinstance(value, str) else ""


def _api_url(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}/releases"


def _final_host_is_api_github(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "https" and parts.hostname == "api.github.com"


def _release_event(repository: str, raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    raw_id = raw.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
        return None
    upstream_id = str(raw_id).strip()
    url = _clean_text(raw.get("html_url"))
    title = _clean_text(raw.get("name")) or _clean_text(raw.get("tag_name"))
    if not upstream_id or not url or not title:
        return None
    description = _clean_text(raw.get("body"))
    published_at = _clean_text(raw.get("published_at")) or None
    return {
        "id": upstream_id,
        "repository": repository,
        "event_kind": "release",
        "url": url,
        "title": title,
        "description": description,
        "published_at": published_at,
    }


def fetch_github_repository_releases(
    *,
    repository: str,
    http_get: Callable[..., Any] = requests.get,
    token: str | None = None,
    timeout_seconds: float = 8.0,
    max_events: int = 5,
) -> list[dict[str, Any]]:
    """Fetch one exact allowlisted repository releases collection."""

    if repository not in GITHUB_REPOSITORIES:
        raise GitHubLiveError(repository, "repository_unapproved")
    if max_events < 1:
        return []
    bounded_events = min(int(max_events), 5)
    url = _api_url(repository)
    kwargs: dict[str, Any] = {
        "params": {"per_page": bounded_events},
        "timeout": float(timeout_seconds),
    }
    if isinstance(token, str) and token:
        kwargs["headers"] = {"Authorization": f"Bearer {token}"}

    try:
        response = http_get(url, **kwargs)
    except Exception:
        raise GitHubLiveError(repository, "request_failure") from None

    final_url = str(getattr(response, "url", url) or url)
    if not _final_host_is_api_github(final_url):
        raise GitHubLiveError(repository, "redirect_host_unapproved")

    try:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        elif int(getattr(response, "status_code", 200) or 200) >= 400:
            raise RuntimeError("HTTP failure")
    except Exception:
        raise GitHubLiveError(repository, "http_failure") from None

    try:
        payload = response.json()
    except Exception:
        raise GitHubLiveError(repository, "invalid_json") from None
    if not isinstance(payload, list):
        raise GitHubLiveError(repository, "invalid_payload")

    events: list[dict[str, Any]] = []
    for raw in payload[:bounded_events]:
        event = _release_event(repository, raw)
        if event is not None:
            events.append(event)

    return acquire_github_candidates(
        repository=repository,
        allowed_repositories=GITHUB_REPOSITORIES,
        events=events,
        max_events=bounded_events,
    )


def fetch_all_github_candidates(
    *,
    http_get: Callable[..., Any] = requests.get,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Read all reviewed repositories; raise only when every repository fails."""

    rows: list[dict[str, Any]] = []
    successful_reads = 0
    for repository in GITHUB_REPOSITORIES:
        try:
            repository_rows = fetch_github_repository_releases(
                repository=repository,
                http_get=http_get,
                token=token,
            )
        except GitHubLiveError:
            continue
        successful_reads += 1
        rows.extend(repository_rows)
    if successful_reads == 0:
        raise GitHubLiveError("GitHub", "all_repositories_failed")
    return rows
