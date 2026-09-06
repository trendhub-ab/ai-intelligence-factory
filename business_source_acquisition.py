"""Run268 business-first source acquisition primitives.

The paid product is not a generic news feed.  Each active source has one explicit
job in the decision product:

* GitHub        -> implementation momentum / OSS maturity
* ArXiv         -> frontier research / technical leading indicators
* HackerNews    -> market and engineer reaction
* OfficialVendor-> commercial primary-source changes

This module intentionally contains no Gemini/model, Notion, or paid-API calls.
HTTP is injected by callers/tests so CI can remain hermetic and fail closed on
accidental network access.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


SOURCE_ROLE_CONTRACT = {
    "GitHub": "implementation_momentum",
    "ArXiv": "frontier_research",
    "HackerNews": "market_engineer_reaction",
    "OfficialVendor": "commercial_primary_source",
}

# One round-robin Source, vendor metadata underneath it.  Keeping vendors inside one
# source prevents a fast-moving vendor/region from taking eleven source slots.
OFFICIAL_VENDOR_REGISTRY = (
    {
        "vendor": "OpenAI",
        "region": "US",
        "release_url": "https://openai.com/products/release-notes/",
        "allowed_domains": ("openai.com",),
    },
    {
        "vendor": "Anthropic",
        "region": "US",
        "release_url": "https://platform.claude.com/docs/en/release-notes/overview",
        "allowed_domains": ("platform.claude.com", "docs.claude.com", "docs.anthropic.com"),
    },
    {
        "vendor": "Google Gemini",
        "region": "US",
        "release_url": "https://ai.google.dev/gemini-api/docs/changelog",
        "allowed_domains": ("ai.google.dev",),
    },
    {
        "vendor": "Alibaba Qwen",
        "region": "CN",
        "release_url": "https://www.alibabacloud.com/help/en/model-studio/model-release-notes",
        "allowed_domains": ("alibabacloud.com",),
    },
    {
        "vendor": "DeepSeek",
        "region": "CN",
        "release_url": "https://api-docs.deepseek.com/updates/",
        "allowed_domains": ("api-docs.deepseek.com", "deepseek.com"),
    },
    {
        "vendor": "ByteDance Doubao/Seed",
        "region": "CN",
        "release_url": "https://www.volcengine.com/docs/82379/1541594?lang=zh",
        "allowed_domains": ("volcengine.com",),
    },
    {
        "vendor": "Moonshot AI Kimi",
        "region": "CN",
        "release_url": "https://platform.kimi.com/docs/models",
        "allowed_domains": ("platform.kimi.com", "kimi.com", "moonshot.cn"),
    },
    {
        "vendor": "Zhipu AI GLM",
        "region": "CN",
        "release_url": "https://docs.bigmodel.cn/cn/update/new-releases",
        "allowed_domains": ("docs.bigmodel.cn", "bigmodel.cn"),
    },
    {
        "vendor": "MiniMax",
        "region": "CN",
        "release_url": "https://platform.minimaxi.com/docs/release-notes/apis",
        "allowed_domains": ("platform.minimaxi.com", "minimaxi.com"),
    },
    {
        "vendor": "Baidu ERNIE",
        "region": "CN",
        "release_url": "https://cloud.baidu.com/doc/qianfan/s/Kmh4stnjp",
        "allowed_domains": ("cloud.baidu.com", "baidu.com"),
    },
    {
        "vendor": "Tencent Hunyuan",
        "region": "CN",
        "release_url": "https://cloud.tencent.com/document/product/1729/132069",
        "allowed_domains": ("cloud.tencent.com", "tencent.com"),
    },
)

# Bounded query set: market/engineer reaction, not the entire HN top-stories firehose.
HN_AI_QUERIES = (
    "AI",
    "LLM",
    "AI agent",
    "OpenAI",
    "Anthropic",
    "Gemini",
    "DeepSeek",
    "Qwen",
)
HN_ALGOLIA_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"

_UPDATE_KEYWORDS = (
    "model", "api", "release", "released", "update", "updated", "changelog",
    "deprecat", "sunset", "retire", "migration", "pricing", "billing", "price",
    "token", "context", "rate limit", "sdk", "openai-compatible", "openai compatible",
    "launch", "preview", "general availability", "ga", "模型", "发布", "上线", "更新",
    "升级", "下线", "退役", "价格", "降价", "计费", "接口", "公告", "迁移", "兼容",
)
_DATE_PATTERN = re.compile(
    r"(?:20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2})",
    re.I,
)


def _response_json(response):
    response.raise_for_status()
    return response.json()


def _response_text(response) -> str:
    response.raise_for_status()
    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content or "")


def _host_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)


def _append_revision_identity(url: str, revision: str) -> str:
    """Create an internal candidate identity without changing the evidence URL.

    Vendor changelog pages often update in place.  ``primaryUrl`` remains the exact
    official page; only the candidate ``url`` gets ``aif_revision`` so a material page
    revision is not permanently hidden by URL dedupe.
    """
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "aif_revision"]
    query.append(("aif_revision", revision[:16]))
    return urlunparse(parsed._replace(query=urlencode(query)))


class _ReleaseHTMLParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._capture_tag = ""
        self._href = ""
        self._buf: list[str] = []
        self.records: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in {"a", "h1", "h2", "h3", "h4", "li", "time"}:
            return
        self._capture_tag = tag
        self._buf = []
        attrs_dict = dict(attrs)
        self._href = attrs_dict.get("href", "") if tag == "a" else ""

    def handle_data(self, data):
        if self._capture_tag:
            self._buf.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag != self._capture_tag:
            return
        text = re.sub(r"\s+", " ", unescape(" ".join(self._buf))).strip()
        href = urljoin(self.base_url, self._href) if self._href else ""
        if text:
            self.records.append((tag, text, href))
        self._capture_tag = ""
        self._href = ""
        self._buf = []


def _extract_vendor_records(html: str, release_url: str, allowed_domains: tuple[str, ...], max_items: int) -> list[dict]:
    parser = _ReleaseHTMLParser(release_url)
    try:
        parser.feed(html or "")
    except Exception:
        # A malformed vendor page should isolate to this vendor, not the whole run.
        return []

    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for tag, text, href in parser.records:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) < 5 or len(compact) > 500:
            continue
        lower = compact.casefold()
        if not any(keyword in lower for keyword in _UPDATE_KEYWORDS):
            continue
        candidate_url = href if href and _host_allowed(href, allowed_domains) else release_url
        key = (candidate_url, compact.casefold())
        if key in seen:
            continue
        seen.add(key)
        date_match = _DATE_PATTERN.search(compact)
        records.append(
            {
                "title": compact[:220],
                "description": compact[:500],
                "url": candidate_url,
                "published_at": date_match.group(0) if date_match else None,
                "html_tag": tag,
            }
        )
        if len(records) >= max_items:
            break
    return records


def _vendor_candidate_from_record(vendor: dict, record: dict, normalize_item) -> dict:
    release_url = vendor["release_url"]
    record_url = record.get("url") or release_url
    identity_material = "\n".join(
        [vendor["vendor"], record.get("title") or "", record.get("description") or "", record.get("published_at") or ""]
    )
    revision = sha256(identity_material.encode("utf-8")).hexdigest()
    # Fragment-only/page-level notes collapse under canonical URL dedupe, so attach an
    # internal revision identity.  Evidence resolution still uses exact primaryUrl.
    url = record_url
    if record_url.rstrip("/") == release_url.rstrip("/") or urlparse(record_url)._replace(fragment="").geturl() == urlparse(release_url)._replace(fragment="").geturl():
        url = _append_revision_identity(release_url, revision)
    item = normalize_item(
        source="OfficialVendor",
        name=f"{vendor['vendor']} — {record.get('title') or 'Official update'}",
        url=url,
        description=record.get("description") or "Official vendor update",
        engagement=0,
        published_at=record.get("published_at"),
        source_context=record.get("description") or record.get("title") or "",
        primary_url=record_url,
        source_details={
            "vendor": vendor["vendor"],
            "vendor_region": vendor["region"],
            "source_role": SOURCE_ROLE_CONTRACT["OfficialVendor"],
            "official_release_url": release_url,
            "candidate_revision": revision[:16],
        },
    )
    return item


def fetch_official_vendor_updates(limit: int, *, normalize_item, http_get, logger=None,
                                  registry=OFFICIAL_VENDOR_REGISTRY) -> list[dict]:
    """Fetch bounded official release-note candidates with per-vendor fault isolation."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_vendor_cap = max(1, min(8, (limit + len(registry) - 1) // max(1, len(registry))))
    buckets: dict[str, deque] = {}

    for vendor in registry:
        try:
            response = http_get(vendor["release_url"], timeout=12, headers={"User-Agent": "AI-Intelligence-Factory/Run268"})
            final_url = str(getattr(response, "url", "") or vendor["release_url"])
            if not _host_allowed(final_url, tuple(vendor["allowed_domains"])):
                raise ValueError(f"redirected outside vendor allowlist: {final_url}")
            html = _response_text(response)
            records = _extract_vendor_records(
                html,
                vendor["release_url"],
                tuple(vendor["allowed_domains"]),
                per_vendor_cap,
            )
            if not records:
                # Page-level fallback is useful once and whenever its visible text changes.
                visible = re.sub(r"<[^>]+>", " ", html)
                visible = re.sub(r"\s+", " ", unescape(visible)).strip()[:500]
                if visible:
                    records = [{
                        "title": "Official release notes / model updates",
                        "description": visible,
                        "url": vendor["release_url"],
                        "published_at": None,
                    }]
            buckets[vendor["vendor"]] = deque(
                _vendor_candidate_from_record(vendor, record, normalize_item) for record in records
            )
            if logger:
                logger.info(f"[OFFICIAL VENDOR] {vendor['vendor']}: {len(buckets[vendor['vendor']])} candidates")
        except Exception as exc:
            buckets[vendor["vendor"]] = deque()
            if logger:
                logger.warning(f"[OFFICIAL VENDOR SKIP] {vendor['vendor']}: {exc}")

    # Vendor-level round robin: vendor velocity must not become source monopoly.
    result: list[dict] = []
    while len(result) < limit and any(buckets.values()):
        for vendor in registry:
            queue = buckets.get(vendor["vendor"])
            if queue:
                result.append(queue.popleft())
                if len(result) >= limit:
                    break
    return result


def _hn_timestamp(created_at: str | None, created_at_i) -> str | None:
    if created_at:
        return str(created_at)
    try:
        return datetime.fromtimestamp(int(created_at_i), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def fetch_hackernews_ai_reactions(limit: int, *, normalize_item, http_get, logger=None,
                                  queries=HN_AI_QUERIES) -> list[dict]:
    """Use bounded Algolia queries to collect AI-related engineer/market reaction."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_query = max(5, min(30, (limit * 2 + len(queries) - 1) // max(1, len(queries))))
    merged: dict[str, dict] = {}

    for query in queries:
        try:
            response = http_get(
                HN_ALGOLIA_ENDPOINT,
                params={"query": query, "tags": "story", "hitsPerPage": per_query},
                timeout=10,
                headers={"User-Agent": "AI-Intelligence-Factory/Run268"},
            )
            payload = _response_json(response)
            for hit in payload.get("hits", []) if isinstance(payload, dict) else []:
                object_id = str(hit.get("objectID") or "").strip()
                title = str(hit.get("title") or "").strip()
                if not object_id or not title:
                    continue
                points = max(0, int(hit.get("points") or 0))
                comments = max(0, int(hit.get("num_comments") or 0))
                existing = merged.get(object_id)
                candidate = {
                    "object_id": object_id,
                    "title": title,
                    "url": str(hit.get("url") or "").strip(),
                    "points": points,
                    "comments": comments,
                    "created_at": hit.get("created_at"),
                    "created_at_i": hit.get("created_at_i"),
                    "query": query,
                }
                if existing is None or (points + comments) > (existing["points"] + existing["comments"]):
                    merged[object_id] = candidate
        except Exception as exc:
            if logger:
                logger.warning(f"[HN AI QUERY SKIP] query={query!r}: {exc}")

    ranked = sorted(
        merged.values(),
        key=lambda row: (row["points"] + row["comments"], row["points"], row.get("created_at_i") or 0),
        reverse=True,
    )[:limit]
    items: list[dict] = []
    for row in ranked:
        hn_url = f"https://news.ycombinator.com/item?id={row['object_id']}"
        external_url = row["url"]
        items.append(
            normalize_item(
                source="HackerNews",
                name=row["title"],
                url=external_url or hn_url,
                description=row["title"],
                engagement=row["points"],
                published_at=_hn_timestamp(row.get("created_at"), row.get("created_at_i")),
                source_context=f"HN points={row['points']} comments={row['comments']} matched_query={row['query']}",
                primary_url=external_url or hn_url,
                source_details={
                    "hn_id": row["object_id"],
                    "hn_url": hn_url,
                    "external_url": external_url,
                    "comments": row["comments"],
                    "matched_query": row["query"],
                    "source_role": SOURCE_ROLE_CONTRACT["HackerNews"],
                },
            )
        )
    if logger:
        logger.info(f"   -> Hacker News AI reaction {len(items)} candidates from {len(queries)} bounded queries.")
    return items
