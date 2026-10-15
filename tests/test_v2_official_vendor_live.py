from __future__ import annotations

import importlib
import importlib.util

import pytest


def _live():
    spec = importlib.util.find_spec("v2_official_vendor_live")
    assert spec is not None, "v2_official_vendor_live must exist"
    return importlib.import_module("v2_official_vendor_live")


class _Response:
    def __init__(self, *, url: str, text: str, status_code: int = 200):
        self.url = url
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: secret-body")


def test_official_vendor_live_sources_are_exact_and_bounded():
    live = _live()
    rows = live.OFFICIAL_VENDOR_SOURCES
    assert [row.provider for row in rows] == ["OpenAI", "Anthropic", "Google Gemini"]
    assert [row.collection_url for row in rows] == [
        "https://openai.com/news",
        "https://www.anthropic.com/news",
        "https://blog.google/products-and-platforms/products/gemini/",
    ]
    assert [row.allowed_hostname for row in rows] == [
        "openai.com",
        "www.anthropic.com",
        "blog.google",
    ]
    assert all(row.max_items == 5 for row in rows)
    assert all(row.timeout_seconds == 8.0 for row in rows)


def test_official_vendor_live_fetch_is_get_only_once_and_uses_existing_normalizer():
    live = _live()
    calls = []
    html = """
    <html><body>
      <article><a href="/index/ai-api-release"><h2>AI API release adds enterprise deployment controls</h2></a></article>
      <article><a href="https://openai.com/index/model-release"><h2>AI model release improves production inference</h2></a></article>
    </body></html>
    """

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(url=url, text=html)

    source = live.OFFICIAL_VENDOR_SOURCES[0]
    result = live.fetch_official_vendor_source(source=source, http_get=http_get)

    assert calls == [("https://openai.com/news", {"timeout": 8.0})]
    assert [item["provider"] for item in result] == ["OpenAI", "OpenAI"]
    assert [item["source_family"] for item in result] == ["official_vendor", "official_vendor"]
    assert [item["primary_url"] for item in result] == [
        "https://openai.com/index/ai-api-release",
        "https://openai.com/index/model-release",
    ]


def test_official_vendor_live_parser_drops_lookalikes_malformed_and_duplicates():
    live = _live()
    html = """
    <html><body>
      <a href="https://openai.com.evil.example/release"><h2>AI release on lookalike host</h2></a>
      <a href="mailto:press@openai.com"><h2>Contact OpenAI press team</h2></a>
      <a href="/news"><h2>OpenAI News</h2></a>
      <a href="/index/release-1?utm_source=feed"><h2>AI API release improves deployment</h2></a>
      <a href="https://openai.com/index/release-1?ref=duplicate"><h2>Duplicate AI API release</h2></a>
    </body></html>
    """

    def http_get(url, **kwargs):
        return _Response(url=url, text=html)

    result = live.fetch_official_vendor_source(
        source=live.OFFICIAL_VENDOR_SOURCES[0],
        http_get=http_get,
    )
    assert len(result) == 1
    assert result[0]["primary_url"] == "https://openai.com/index/release-1"


def test_official_vendor_live_caps_items_before_normalization():
    live = _live()
    anchors = "".join(
        f'<a href="/index/release-{index}"><h2>AI release {index} improves deployment workflow</h2></a>'
        for index in range(10)
    )

    def http_get(url, **kwargs):
        return _Response(url=url, text=f"<html><body>{anchors}</body></html>")

    result = live.fetch_official_vendor_source(
        source=live.OFFICIAL_VENDOR_SOURCES[0],
        http_get=http_get,
    )
    assert len(result) == 5


def test_official_vendor_live_rejects_redirect_escape_without_leaking_body():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(
            url="https://evil.example/redirected",
            text="secret raw vendor body",
        )

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_official_vendor_source(
            source=live.OFFICIAL_VENDOR_SOURCES[0],
            http_get=http_get,
        )
    assert excinfo.value.category == "redirect_host_unapproved"
    assert "secret raw vendor body" not in str(excinfo.value)


def test_official_vendor_live_http_failure_has_safe_category_without_raw_text():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, text="secret-body", status_code=503)

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_official_vendor_source(
            source=live.OFFICIAL_VENDOR_SOURCES[0],
            http_get=http_get,
        )
    assert excinfo.value.category == "http_failure"
    assert "secret-body" not in str(excinfo.value)


def test_official_vendor_live_empty_supported_surface_returns_empty_without_fallback():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, text="<html><body><p>No supported article anchors</p></body></html>")

    assert live.fetch_official_vendor_source(
        source=live.OFFICIAL_VENDOR_SOURCES[0],
        http_get=http_get,
    ) == []
