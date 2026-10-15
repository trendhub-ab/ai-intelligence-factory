"""Bounded, read-only acquisition normalization for official vendor sources.

V2 shadow only. This adapter deliberately accepts already-fetched source items and
an explicitly configured endpoint; it performs no crawling, discovery, model
calls, persistence, or Production mutation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
}


def _canonicalize_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
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
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(kept_query, doseq=True),
            "",
        )
    )


def _exact_hostname(url: str) -> str | None:
    try:
        return urlsplit(url).hostname.lower() if urlsplit(url).hostname else None
    except ValueError:
        return None


def acquire_official_vendor_candidates(
    *,
    endpoint_url: str,
    allowed_endpoints: Iterable[str],
    provider: str,
    allowed_domains: Iterable[str],
    items: Iterable[Mapping[str, Any]],
    max_items: int = 10,
) -> list[dict[str, Any]]:
    """Normalize bounded official-vendor items into the V2 candidate contract.

    The endpoint itself must be explicitly allowlisted. Candidate URLs must use
    an exact configured hostname; lookalike suffixes are rejected. Malformed
    items are skipped fail-closed. Input order is preserved, canonical URL
    duplicates are removed, and the result is capped by ``max_items``.
    """

    if max_items < 1:
        raise ValueError("max_items must be at least 1")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("provider is required")

    allowed_endpoint_set = {
        endpoint.strip() for endpoint in allowed_endpoints if isinstance(endpoint, str) and endpoint.strip()
    }
    if endpoint_url not in allowed_endpoint_set:
        raise ValueError("endpoint must be explicitly allowlisted")

    domain_set = {
        domain.strip().lower().rstrip(".")
        for domain in allowed_domains
        if isinstance(domain, str) and domain.strip()
    }
    if not domain_set:
        raise ValueError("allowed_domains must not be empty")

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in items:
        if len(results) >= max_items:
            break
        if not isinstance(item, Mapping):
            continue

        raw_url = item.get("url") or item.get("primary_url")
        canonical_url = _canonicalize_url(raw_url)
        if canonical_url is None:
            continue
        hostname = _exact_hostname(canonical_url)
        if hostname not in domain_set:
            continue

        upstream_id = item.get("id") or item.get("upstream_id")
        title = item.get("title")
        if not isinstance(upstream_id, str) or not upstream_id.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if canonical_url in seen_urls:
            continue

        description = item.get("description")
        published_at = item.get("published_at")
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
                "source_family": "official_vendor",
                "provider": provider.strip(),
                "canonical_url": canonical_url,
                "upstream_id": upstream_id.strip(),
            }
        )

    return results
