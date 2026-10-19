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
    assert [row.provider for row in rows] == [
        "OpenAI", "Anthropic", "Google Gemini", "Microsoft", "Meta",
        "Google DeepMind", "NVIDIA", "Mistral",
    ]
    assert [row.collection_url for row in rows] == [
        "https://openai.com/news",
        "https://www.anthropic.com/news",
        "https://blog.google/products-and-platforms/products/gemini/",
        "https://www.microsoft.com/en-us/research/blog/",
        "https://ai.meta.com/blog/",
        "https://deepmind.google/blog/rss.xml",
        "https://developer.nvidia.com/blog/feed/",
        "https://mistral.ai/news/rss",
    ]
    assert [row.allowed_hostname for row in rows] == [
        "openai.com",
        "www.anthropic.com",
        "blog.google",
        "www.microsoft.com",
        "ai.meta.com",
        "deepmind.google",
        "developer.nvidia.com",
        "mistral.ai",
    ]
    assert [row.allowed_path_prefixes for row in rows] == [
        ("/index/",),
        ("/news/",),
        (
            "/products-and-platforms/products/gemini/",
            "/innovation-and-ai/models-and-research/gemini-models/",
        ),
        ("/en-us/research/blog/",),
        ("/blog/",),
        ("/blog/",),
        ("/blog/",),
        ("/news/",),
    ]
    assert all(row.max_items == 5 for row in rows)
    assert all(row.timeout_seconds == 8.0 for row in rows)
    assert [row.response_format for row in rows] == [
        "html", "html", "html", "html", "html", "feed", "feed", "feed"
    ]


@pytest.mark.parametrize(
    ("provider", "article_path"),
    [
        ("Microsoft", "/en-us/research/blog/next-generation-ai-research/"),
        ("Meta", "/blog/next-generation-ai-research/"),
    ],
)
def test_new_vendor_source_extracts_only_same_host_article_links(provider, article_path):
    live = _live()
    source = next(source for source in live.OFFICIAL_VENDOR_SOURCES if source.provider == provider)
    html = f"""
    <a href="{source.collection_url}"><h2>Collection page</h2></a>
    <a href="https://{source.allowed_hostname}.evil.example{article_path}"><h2>Impersonation</h2></a>
    <a href="https://evil.example{article_path}"><h2>Off-site article</h2></a>
    <a href="/careers/engineer"><h2>Off-topic navigation</h2></a>
    <a href="{article_path}?utm_source=homepage"><h2>AI research improves model deployment</h2></a>
    <a href="{article_path}?ref=duplicate"><h2>Duplicate announcement</h2></a>
    """
    calls = []

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(url=url, text=html)

    result = live.fetch_official_vendor_source(source=source, http_get=http_get)
    assert calls == [(source.collection_url, {"timeout": 8.0})]
    assert len(result) == 1
    assert result[0]["provider"] == provider
    assert result[0]["title"] == "AI research improves model deployment"
    assert result[0]["primary_url"] == f"https://{source.allowed_hostname}{article_path}"


@pytest.mark.parametrize(
    ("provider", "article_path", "feed_kind"),
    [
        ("Google DeepMind", "/blog/next-generation-ai-research/", "rss"),
        ("NVIDIA", "/blog/next-generation-ai-research/", "atom"),
        ("Mistral", "/news/next-generation-ai-research/", "rss"),
    ],
)
def test_new_vendor_feeds_extract_only_safe_article_links(provider, article_path, feed_kind):
    live = _live()
    source = next(source for source in live.OFFICIAL_VENDOR_SOURCES if source.provider == provider)
    valid_url = f"https://{source.allowed_hostname}{article_path}"
    spoof_url = f"https://{source.allowed_hostname}.evil.example{article_path}"
    if feed_kind == "rss":
        html = f"""<rss version="2.0"><channel>
            <item><title>AI model research improves deployment</title><link>{valid_url}</link></item>
            <item><title>Impersonation</title><link>{spoof_url}</link></item>
            <item><title>Duplicate</title><link>{valid_url}?utm_source=feed</link></item>
            <item><title>Navigation</title><link>https://{source.allowed_hostname}/careers/</link></item>
        </channel></rss>"""
    else:
        html = f"""<feed xmlns="http://www.w3.org/2005/Atom">
            <entry><title>AI model research improves deployment</title><link rel="alternate" href="{valid_url}"/></entry>
            <entry><title>Impersonation</title><link href="{spoof_url}"/></entry>
            <entry><title>Duplicate</title><link href="{valid_url}?ref=duplicate"/></entry>
            <entry><title>Navigation</title><link href="https://{source.allowed_hostname}/careers/"/></entry>
        </feed>"""
    calls = []

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(url=url, text=html)

    result = live.fetch_official_vendor_source(source=source, http_get=http_get)
    assert calls == [(source.collection_url, {"timeout": 8.0})]
    assert [row["primary_url"] for row in result] == [valid_url]
    assert result[0]["provider"] == provider


def test_new_vendor_feed_rejects_malformed_xml_without_leaking_payload():
    live = _live()
    source = next(source for source in live.OFFICIAL_VENDOR_SOURCES if source.provider == "NVIDIA")

    def http_get(url, **kwargs):
        return _Response(url=url, text="<secret token=do-not-log><entry></secret>")

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_official_vendor_source(source=source, http_get=http_get)
    assert excinfo.value.category == "invalid_feed"
    assert "do-not-log" not in str(excinfo.value)


def test_all_eight_vendor_sources_keep_get_budget_and_isolate_single_failure():
    live = _live()
    calls = []
    failing_source = "https://deepmind.google/blog/rss.xml"

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        if url == failing_source:
            raise RuntimeError("opaque vendor failure")
        return _Response(url=url, text="<html><body></body></html>")

    assert live.fetch_all_official_vendor_candidates(http_get=http_get) == []
    assert [url for url, _ in calls] == [source.collection_url for source in live.OFFICIAL_VENDOR_SOURCES]
    assert all(kwargs == {"timeout": 8.0} for _, kwargs in calls)


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

    result = live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert calls == [("https://openai.com/news", {"timeout": 8.0})]
    assert [item["provider"] for item in result] == ["OpenAI", "OpenAI"]
    assert [item["primary_url"] for item in result] == [
        "https://openai.com/index/ai-api-release",
        "https://openai.com/index/model-release",
    ]


def test_official_vendor_live_ignores_same_host_navigation_before_article_cards():
    live = _live()
    html = """
    <html><body>
      <a href="/news/company-announcements/">Company</a>
      <a href="/research/">Research</a>
      <a href="/business/">Business</a>
      <a href="/index/release-1"><span>Product</span><h2>AI API release improves deployment</h2><span>Aug 7, 2026</span></a>
      <a href="/index/release-2"><h3>New reasoning model improves enterprise workflow</h3></a>
    </body></html>
    """

    def http_get(url, **kwargs):
        return _Response(url=url, text=html)

    result = live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert [row["primary_url"] for row in result] == [
        "https://openai.com/index/release-1",
        "https://openai.com/index/release-2",
    ]
    assert result[0]["title"] == "AI API release improves deployment"


def test_official_vendor_live_parser_drops_lookalikes_malformed_and_duplicates():
    live = _live()
    html = """
    <html><body>
      <a href="https://openai.com.evil.example/index/release"><h2>AI release on lookalike host</h2></a>
      <a href="mailto:press@openai.com"><h2>Contact OpenAI press team</h2></a>
      <a href="/news"><h2>OpenAI News</h2></a>
      <a href="/index/release-1?utm_source=feed"><h2>AI API release improves deployment</h2></a>
      <a href="https://openai.com/index/release-1?ref=duplicate"><h2>Duplicate AI API release</h2></a>
    </body></html>
    """

    def http_get(url, **kwargs):
        return _Response(url=url, text=html)

    result = live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert len(result) == 1
    assert result[0]["primary_url"] == "https://openai.com/index/release-1"


def test_official_vendor_live_caps_approved_articles_not_navigation_links():
    live = _live()
    nav = "".join(f'<a href="/news/category-{i}/">Category {i}</a>' for i in range(10))
    articles = "".join(
        f'<a href="/index/release-{index}"><h2>AI release {index} improves deployment workflow</h2></a>'
        for index in range(10)
    )

    def http_get(url, **kwargs):
        return _Response(url=url, text=f"<html><body>{nav}{articles}</body></html>")

    result = live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert len(result) == 5
    assert all("/index/release-" in row["primary_url"] for row in result)


def test_official_vendor_live_rejects_redirect_escape_without_leaking_body():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url="https://evil.example/redirected", text="secret raw vendor body")

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert excinfo.value.category == "redirect_host_unapproved"
    assert "secret raw vendor body" not in str(excinfo.value)


def test_official_vendor_live_http_failure_has_safe_category_without_raw_text():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, text="secret-body", status_code=503)

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get)
    assert excinfo.value.category == "http_failure"
    assert "secret-body" not in str(excinfo.value)


def test_official_vendor_live_empty_supported_surface_returns_empty_without_fallback():
    live = _live()

    def http_get(url, **kwargs):
        return _Response(url=url, text="<html><body><p>No supported article anchors</p></body></html>")

    assert live.fetch_official_vendor_source(source=live.OFFICIAL_VENDOR_SOURCES[0], http_get=http_get) == []


def test_official_vendor_live_all_vendor_failures_raise_family_failure():
    live = _live()

    def http_get(url, **kwargs):
        raise RuntimeError("secret outage")

    with pytest.raises(live.VendorLiveError) as excinfo:
        live.fetch_all_official_vendor_candidates(http_get=http_get)
    assert excinfo.value.provider == "OfficialVendor"
    assert excinfo.value.category == "all_sources_failed"
    assert "secret outage" not in str(excinfo.value)


def test_official_vendor_live_partial_failure_remains_isolated():
    live = _live()

    def http_get(url, **kwargs):
        if url == "https://openai.com/news":
            raise RuntimeError("one vendor down")
        return _Response(url=url, text="<html><body></body></html>")

    assert live.fetch_all_official_vendor_candidates(http_get=http_get) == []
