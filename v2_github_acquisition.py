"""Bounded, read-only normalization for allowlisted GitHub release metadata.

V2 shadow only. The adapter consumes already-fetched metadata for one explicitly
allowlisted repository. It performs no GitHub-wide discovery, authenticated
write, model call, persistence, or Production mutation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_ALLOWED_EVENT_KINDS = frozenset({"release", "tag", "changelog"})
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "ref", "source"}


def _canonicalize_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or parts.hostname != "github.com":
        return None
    kept_query = []
    for key, item_value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS:
            continue
        kept_query.append((key, item_value))
    return urlunsplit(
        (
            parts.scheme.lower(),
            "github.com",
            parts.path or "/",
            urlencode(kept_query, doseq=True),
            "",
        )
    )


def _belongs_to_repository(url: str, repository: str) -> bool:
    path = urlsplit(url).path.rstrip("/")
    prefix = f"/{repository}"
    return path == prefix or path.startswith(prefix + "/")


def acquire_github_candidates(
    *,
    repository: str,
    allowed_repositories: Iterable[str],
    events: Iterable[Mapping[str, Any]],
    max_events: int = 10,
) -> list[dict[str, Any]]:
    """Normalize bounded GitHub release/tag/changelog events.

    ``repository`` must exactly match the configured allowlist. Each accepted
    event must identify that same repository, use github.com beneath that repo,
    and be one of the explicitly supported event kinds. Malformed or ambiguous
    events are dropped fail-closed. Input order is preserved and canonical URL
    duplicates are removed.
    """

    if max_events < 1:
        raise ValueError("max_events must be at least 1")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("repository is required")

    repository = repository.strip()
    allowed = {
        value.strip()
        for value in allowed_repositories
        if isinstance(value, str) and value.strip()
    }
    if repository not in allowed:
        raise ValueError("repository must be exactly allowlisted")

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for event in events:
        if len(results) >= max_events:
            break
        if not isinstance(event, Mapping):
            continue
        if event.get("repository") != repository:
            continue

        event_kind = event.get("event_kind")
        if event_kind not in _ALLOWED_EVENT_KINDS:
            continue

        canonical_url = _canonicalize_url(event.get("url") or event.get("primary_url"))
        if canonical_url is None or not _belongs_to_repository(canonical_url, repository):
            continue
        if canonical_url in seen_urls:
            continue

        upstream_id = event.get("id") or event.get("upstream_id")
        title = event.get("title")
        if not isinstance(upstream_id, str) or not upstream_id.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue

        description = event.get("description")
        published_at = event.get("published_at")
        if description is not None and not isinstance(description, str):
            continue
        if published_at is not None and not isinstance(published_at, str):
            continue

        seen_urls.add(canonical_url)
        results.append(
            {
                "primary_url": canonical_url,
                "title": title.strip(),
                "description": description.strip() if isinstance(description, str) else "",
                "published_at": published_at,
                "source_family": "github",
                "provider": "GitHub",
                "repository": repository,
                "event_kind": event_kind,
                "canonical_url": canonical_url,
                "upstream_id": upstream_id.strip(),
            }
        )

    return results
