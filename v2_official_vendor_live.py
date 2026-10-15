"""Bounded GET-only OfficialVendor live reader for V2-005C shadow proof.

This module reads only the exact reviewed vendor collection pages, extracts a
small set of same-host article links, and delegates normalization to the
existing V2-005B OfficialVendor adapter. It performs no discovery, crawling,
article-detail fetch, model call, persistence, or Production mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

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
    max_items: int = 5
    timeout_seconds: float = 8.0


OFFICIAL_VENDOR_SOURCES: tuple[VendorSourceConfig, ...] = (
    VendorSourceConfig(
        provider="OpenAI",
        collection_url="https://openai.com/news",
        allowed_hostname="openai.com",
    ),
    VendorSourceConfig(
        provider="Anthropic",
        collection_url="https://www.anthropic.com/news",
        allowed_hostname="www.anthropic.com",
    ),
    VendorSourceConfig(
        provider="Google Gemini",
        collection_url="https://blog.google/products-and-platforms/products/gemini/",
        allowed_hostname="blog.google",
    ),
)


def _clean_text(value: object) -> str:
    return " ".join(value.split()).strip() if isinstance(value, str) else ""


def _canonical_page_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._depth = 0
        self._text: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a" and self._href is None:
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            if isinstance(href, str):
                self._href = href
                self._depth = 1
                self._text = []
                return
        if self._href is not None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._href is None:
            return
        if self._depth > 1:
            self._depth -= 1
            return
        if tag.lower() == "a":
            title = _clean_text(" ".join(self._text))
            self.anchors.append((self._href, title))
            self._href = None
            self._depth = 0
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            text = _clean_text(data)
            if text:
                self._text.append(text)


def _same_allowed_host(url: str, allowed_hostname: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and parts.hostname == allowed_hostname


def fetch_official_vendor_source(
    *,
    source: VendorSourceConfig,
    http_get: Callable[..., Any] = requests.get,
) -> list[dict[str, Any]]:
    """Fetch one exact allowlisted vendor collection page and normalize <=5 links."""

    try:
        response = http_get(source.collection_url, timeout=source.timeout_seconds)
    except Exception:
        raise VendorLiveError(source.provider, "request_failure") from None

    final_url = str(getattr(response, "url", source.collection_url) or source.collection_url)
    if not _same_allowed_host(final_url, source.allowed_hostname):
        raise VendorLiveError(source.provider, "redirect_host_unapproved")

    try:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        elif int(getattr(response, "status_code", 200) or 200) >= 400:
            raise RuntimeError("HTTP failure")
    except Exception:
        raise VendorLiveError(source.provider, "http_failure") from None

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
) -> list[dict[str, Any]]:
    """Read the three reviewed vendor pages in stable order, isolating failures."""

    rows: list[dict[str, Any]] = []
    for source in OFFICIAL_VENDOR_SOURCES:
        try:
            rows.extend(fetch_official_vendor_source(source=source, http_get=http_get))
        except VendorLiveError:
            continue
    return rows
