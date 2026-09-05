"""Deterministic candidate URL identity helpers extracted from pipeline.py (Run241).

Stdlib-only, zero-network and zero-provider. The canonicalization contract is intentionally
conservative: only known tracking parameters and URL presentation differences are removed.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_DEDUP_IGNORED_QUERY_PREFIXES = ("utm_",)
_DEDUP_IGNORED_QUERY_KEYS = {"fbclid", "gclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    """URL Dedup専用の正規化。意味のあるpath/queryは変更しない。"""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    netloc = (parsed.netloc or "").lower()
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    path = parsed.path.rstrip("/")
    if netloc in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(r"/(abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path, re.I)
        if match:
            path = f"/abs/{match.group(2)}"
            netloc = "arxiv.org"
            scheme = "https"
    filtered_query = sorted(
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith(_DEDUP_IGNORED_QUERY_PREFIXES)
        and k.lower() not in _DEDUP_IGNORED_QUERY_KEYS
    )
    return urlunparse((scheme, netloc, path, "", urlencode(filtered_query, doseq=True), ""))


def candidate_identity_urls(repo: dict, *, canonicalizer=canonicalize_url) -> set[str]:
    """Cross-source dedupe用の保守的な同一性URL集合。"""
    raw_urls: list[str] = []
    for value in (repo.get("url"), repo.get("primaryUrl")):
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    details = repo.get("sourceDetails") or {}
    for key in (
        "external_url", "official_url", "officialUrl", "website", "website_url",
        "homepage", "project_url", "docs_url", "documentation_url", "hn_url", "producthunt_url",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    for key in ("official_external_links", "links", "related_links"):
        values = details.get(key) or []
        if isinstance(values, (list, tuple, set)):
            raw_urls.extend(v.strip() for v in values if isinstance(v, str) and v.strip())
    return {canonicalizer(u) for u in raw_urls if canonicalizer(u)}
