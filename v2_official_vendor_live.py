"""Bounded GET-only OfficialVendor live reader for V2-005C shadow proof.

This module reads only the exact reviewed vendor collection pages, extracts a
small set of same-host article links under reviewed path prefixes, and delegates
normalization to the existing V2-005B OfficialVendor adapter. It performs no
discovery, crawling, article-detail fetch, model call, persistence, or Production
mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import time
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from v2_live_shadow_acquisition import AcquisitionRequestError, bounded_get
from v2_official_vendor_acquisition import acquire_official_vendor_candidates


class VendorLiveError(RuntimeError):
    """Safe categorical OfficialVendor live-read failure."""

    def __init__(self, provider: str, category: str) -> None:
        self.provider = str(provider)
        self.category = str(category)
        super().__init__(f"{self.provider}:{self.category}")


@dataclass(frozen=True)
class VendorSourceConfig:
    provider: str
    collection_url: str
    allowed_hostname: str
    allowed_path_prefixes: tuple[str, ...]
    max_items: int = 5
    timeout_seconds: float = 8.0


OFFICIAL_VENDOR_SOURCES: tuple[VendorSourceConfig, ...] = (
    VendorSourceConfig(
        provider="OpenAI",
        collection_url="https://openai.com/news",
        allowed_hostname="openai.com",
        allowed_path_prefixes=("/index/",),
    ),
    VendorSourceConfig(
        provider="Anthropic",
        collection_url="https://www.anthropic.com/news",
        allowed_hostname="www.anthropic.com",
        allowed_path_prefixes=("/news/",),
    ),
    VendorSourceConfig(
        provider="Google Gemini",
        collection_url="https://blog.google/products-and-platforms/products/gemini/",
        allowed_hostname="blog.google",
        allowed_path_prefixes=(
            "/products-and-platforms/products/gemini/",
            "/innovation-and-ai/models-and-research/gemini-models/",
        ),
    ),
)


def _clean_text(value: object) -> str:
    return " ".join(value.split()).strip() if isinstance(value, str) else ""


def _canonical_page_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


class _AnchorParser(HTMLParser):
    _HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._depth = 0
        self._text: list[str] = []
        self._heading_depth: int | None = None
        self._heading_text: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "a" and self._href is None:
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            if isinstance(href, str):
                self._href = href
                self._depth = 1
                self._text = []
                self._heading_depth = None
                self._heading_text = []
                return
        if self._href is not None:
            self._depth += 1
            if lowered in self._HEADING_TAGS and self._heading_depth is None:
                self._heading_depth = self._depth

    def handle_endtag(self, tag: str) -> None:
        if self._href is None:
            return
        lowered = tag.lower()
        if self._heading_depth == self._depth and lowered in self._HEADING_TAGS:
            self._heading_depth = None
        if self._depth > 1:
            self._depth -= 1
            return
        if lowered == "a":
            heading = _clean_text(" ".join(self._heading_text))
            title = heading or _clean_text(" ".join(self._text))
            self.anchors.append((self._href, title))
            self._href = None
            self._depth = 0
            self._text = []
            self._heading_text = []

    def handle_data(self, data: str) -> None:
        if self._href is None:
            return
        text = _clean_text(data)
        if not text:
            return
        self._text.append(text)
        if self._heading_depth is not None:
            self._heading_text.append(text)


def _same_allowed_host(url: str, allowed_hostname: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and parts.hostname == allowed_hostname


def _approved_article_path(url: str, prefixes: tuple[str, ...]) -> bool:
    try:
        path = urlsplit(url).path
    except ValueError:
        return False
    return any(path.startswith(prefix) and path.rstrip("/") != prefix.rstrip("/") for prefix in prefixes)


def fetch_official_vendor_source(
    *,
    source: VendorSourceConfig,
    http_get: Callable[..., Any] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
    diagnostic_sink: Callable[[Mapping[str, object]], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch one exact allowlisted vendor collection page and normalize <=5 links."""

    try:
        response, _diagnostics = bounded_get(
            http_get=http_get,
            url=source.collection_url,
            timeout=source.timeout_seconds,
            sleep_fn=sleep_fn,
            diagnostic_sink=diagnostic_sink,
        )
    except AcquisitionRequestError as exc:
        raise VendorLiveError(source.provider, exc.category) from None

    final_url = str(getattr(response, "url", source.collection_url) or source.collection_url)
    if not _same_allowed_host(final_url, source.allowed_hostname):
        raise VendorLiveError(source.provider, "redirect_host_unapproved")

    html = getattr(response, "text", None)
    if not isinstance(html, str):
        raise VendorLiveError(source.provider, "invalid_html")

    parser = _AnchorParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        raise VendorLiveError(source.provider, "invalid_html") from None

    collection_identity = _canonical_page_url(source.collection_url)
    items: list[dict[str, Any]] = []
    for href, title in parser.anchors:
        if len(items) >= source.max_items:
            break
        if not title:
            continue
        absolute = urljoin(source.collection_url, href)
        if not _same_allowed_host(absolute, source.allowed_hostname):
            continue
        if _canonical_page_url(absolute) == collection_identity:
            continue
        if not _approved_article_path(absolute, source.allowed_path_prefixes):
            continue
        items.append(
            {
                "id": absolute,
                "url": absolute,
                "title": title,
                "description": "",
                "published_at": None,
            }
        )

    return acquire_official_vendor_candidates(
        endpoint_url=source.collection_url,
        allowed_endpoints={source.collection_url},
        provider=source.provider,
        allowed_domains={source.allowed_hostname},
        items=items,
        max_items=source.max_items,
    )


def fetch_all_official_vendor_candidates(
    *,
    http_get: Callable[..., Any] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
    diagnostic_sink: Callable[[Mapping[str, object]], None] | None = None,
) -> list[dict[str, Any]]:
    """Read the three reviewed vendor pages; raise only when all three fail."""

    rows: list[dict[str, Any]] = []
    successful_reads = 0
    for source in OFFICIAL_VENDOR_SOURCES:
        try:
            source_rows = fetch_official_vendor_source(
                source=source,
                http_get=http_get,
                sleep_fn=sleep_fn,
                diagnostic_sink=diagnostic_sink,
            )
        except VendorLiveError:
            continue
        successful_reads += 1
        rows.extend(source_rows)
    if successful_reads == 0:
        raise VendorLiveError("OfficialVendor", "all_sources_failed")
    return rows
