from __future__ import annotations

import re
from typing import Iterable, List, Mapping, MutableSet, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.IGNORECASE)
_TRACKING_KEYS = {"fbclid", "gclid", "dclid", "msclkid", "ref", "ref_src"}
_INTERNAL_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
_SHORTENER_HOSTS = {"t.co", "www.t.co"}
_PRIMARY_SOURCE_SUFFIXES = (
    "github.com",
    "arxiv.org",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.google.dev",
    "developers.googleblog.com",
    "huggingface.co",
    "microsoft.com",
    "meta.com",
)
_TRAILING_PUNCTUATION = ".,;:!?)]}>、。！？）」』】"


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_internal_x_url(url: str) -> bool:
    return _host(url) in _INTERNAL_X_HOSTS


def is_unresolved_short_url(url: str) -> bool:
    return _host(url) in _SHORTENER_HOSTS


def canonicalize_url(url: str) -> Optional[str]:
    raw = (url or "").strip().rstrip(_TRAILING_PUNCTUATION)
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None

    host = parts.hostname.lower()
    if parts.port:
        default = (parts.scheme.lower() == "https" and parts.port == 443) or (
            parts.scheme.lower() == "http" and parts.port == 80
        )
        netloc = host if default else f"{host}:{parts.port}"
    else:
        netloc = host

    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_KEYS:
            continue
        query_items.append((key, value))
    query_items.sort()

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query_items, doseq=True), ""))


def _structured_urls(record: Mapping[str, object]) -> Iterable[str]:
    containers = []
    entities = record.get("entities")
    if isinstance(entities, Mapping):
        containers.append(entities.get("urls"))
    containers.append(record.get("urls"))

    for container in containers:
        if not isinstance(container, list):
            continue
        for item in container:
            if isinstance(item, str):
                yield item
                continue
            if not isinstance(item, Mapping):
                continue
            for key in ("expanded_url", "expandedUrl", "unwound_url", "unwoundUrl", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    yield value
                    break


def extract_external_urls(record: Mapping[str, object], text: str) -> List[str]:
    seen: MutableSet[str] = set()
    result: List[str] = []
    raw_urls = list(_structured_urls(record)) + _URL_RE.findall(text or "")
    for raw in raw_urls:
        canonical = canonicalize_url(raw)
        if not canonical:
            continue
        if is_internal_x_url(canonical) or is_unresolved_short_url(canonical):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


def is_primary_source_candidate(url: str) -> bool:
    host = _host(url)
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in _PRIMARY_SOURCE_SUFFIXES)
