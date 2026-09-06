"""Run268/269 business-first source acquisition primitives.

The paid product is not a generic news feed. Each active source has one explicit
job in the decision product:

* GitHub         -> implementation momentum / OSS maturity
* ArXiv          -> frontier research / technical leading indicators
* HackerNews     -> market and engineer reaction
* OfficialVendor -> commercial primary-source changes

Run269 hardens the live acquisition surface after the first real-network smoke:
- vendor navigation labels must not masquerade as release candidates;
- vendor candidates prefer structured post-heading update content over page fallback;
- HN is title-scoped, freshness-bounded, and no longer uses the over-broad ``AI`` query.

This module intentionally contains no Gemini/model, Notion, or paid-API calls.
HTTP is injected by callers/tests so deterministic CI can remain hermetic.
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

# One round-robin Source, vendor metadata underneath it. Keeping vendors inside one
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
        # The previous announcement index was reachable but JS-heavy and produced only
        # a page fallback in the first live smoke. The official "latest model" page is
        # server-readable and changes when the commercially current Seed model changes.
        "release_url": "https://www.volcengine.com/docs/82379/2549861?lang=zh",
        "allowed_domains": ("volcengine.com",),
    },
    {
        "vendor": "Moonshot AI Kimi",
        "region": "CN",
        # Model list is also the official retirement/migration surface (for example,
        # retired kimi-k2/kimi-latest notices), so it is commercially decision-relevant.
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
        # Run269 switched from the stale API-function log (latest 2025 in the live
        # surface) to the current official model-release page with 2026 releases.
        "release_url": "https://platform.minimaxi.com/docs/release-notes/models",
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
        # Product dynamics contains model launch/retirement/migration events with dates;
        # it is more useful for selection decisions than the generic announcement index.
        "release_url": "https://cloud.tencent.com/document/product/1729/97765",
        "allowed_domains": ("cloud.tencent.com", "tencent.com"),
    },
)

# High-precision bounded query set. The first live smoke proved that raw ``AI`` was
# too broad (e.g. unrelated titles were returned). Algolia is additionally restricted
# to title matching below, so HN measures explicit engineer/community reaction to AI.
HN_AI_QUERIES = (
    '"artificial intelligence"',
    '"large language model"',
    "LLM",
    '"AI agent"',
    '"coding agent"',
    "OpenAI",
    "Anthropic",
    "Claude",
    "Gemini",
    "DeepSeek",
    "Qwen",
)
HN_ALGOLIA_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"
HN_LOOKBACK_DAYS = 30

# Strong change language. Generic navigation words such as "model", "API", "pricing",
# and "token" are intentionally NOT sufficient on their own.
_UPDATE_ACTION_KEYWORDS = (
    "release", "released", "releasing", "update", "updated", "upgrade", "upgraded",
    "change", "changed", "changelog", "deprecat", "sunset", "retire", "retired",
    "migration", "migrate", "price reduction", "price increase", "price adjustment",
    "pricing change", "rate limit", "launch", "launched", "general availability",
    "discontinued", "shut down", "removed", "added", "introducing", "can now",
    "now supports", "latest model", "new model",
    "发布", "上线", "上新", "更新", "升级", "下线", "退役", "降价", "涨价",
    "价格调整", "价格变更", "新增", "停止", "停用", "废弃", "迁移", "变更",
    "最新模型", "新品", "重磅推出", "正式发布",
)
_VENDOR_SUBJECT_KEYWORDS = (
    "model", "api", "sdk", "agent", "token", "context", "inference", "tool",
    "webhook", "pricing", "price", "billing", "rate limit", "compatib",
    "模型", "接口", "智能体", "上下文", "推理", "工具", "价格", "计费", "调用",
    "服务", "兼容", "编码", "coding",
)
_GENERIC_PAGE_HEADINGS = {
    "release notes",
    "change log",
    "changelog",
    "model release notes",
    "新品发布",
    "功能更新",
    "模型发布",
    "模型列表",
    "模型更新记录",
    "产品动态",
    "产品公告",
    "产品更新公告",
    "模型发布公告",
}
_DATE_PATTERN = re.compile(
    r"(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|"
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
    """Create an internal candidate identity without changing the evidence URL."""
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "aif_revision"]
    query.append(("aif_revision", revision[:16]))
    return urlunparse(parsed._replace(query=urlencode(query)))


class _ReleaseHTMLParser(HTMLParser):
    """Capture useful text blocks while preserving nested parent text (e.g. table rows)."""

    _SUPPORTED = {"a", "h1", "h2", "h3", "h4", "li", "time", "p", "blockquote", "tr", "td", "th", "button"}

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._captures: list[dict] = []
        self.records: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self._SUPPORTED:
            return
        attrs_dict = dict(attrs)
        href = urljoin(self.base_url, attrs_dict.get("href", "")) if tag == "a" and attrs_dict.get("href") else ""
        self._captures.append({"tag": tag, "href": href, "buf": []})

    def handle_data(self, data):
        for capture in self._captures:
            capture["buf"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self._captures:
            return
        # Close only the nearest matching supported capture. Malformed HTML is common;
        # unmatched wrappers are left for HTMLParser to continue rather than raising.
        index = None
        for i in range(len(self._captures) - 1, -1, -1):
            if self._captures[i]["tag"] == tag:
                index = i
                break
        if index is None:
            return
        capture = self._captures.pop(index)
        text = re.sub(r"\s+", " ", unescape(" ".join(capture["buf"]))).strip()
        if text:
            self.records.append((tag, text, capture["href"]))


def _normalized_heading(text: str) -> str:
    return re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", " ", (text or "").casefold()).strip()


def _is_generic_page_heading(text: str) -> bool:
    return _normalized_heading(text) in {_normalized_heading(value) for value in _GENERIC_PAGE_HEADINGS}


def _looks_like_vendor_update(tag: str, compact: str, current_date: str | None) -> bool:
    lower = compact.casefold()
    strong_change = any(keyword in lower for keyword in _UPDATE_ACTION_KEYWORDS)
    subject = any(keyword in lower for keyword in _VENDOR_SUBJECT_KEYWORDS)
    if strong_change and len(compact) >= 10:
        return True
    # Dated list/table prose can describe a change without an explicit verb (common on
    # Anthropic/Baidu/Tencent). Require both meaningful length and a technical subject.
    if current_date and tag in {"li", "p", "blockquote", "tr", "td"} and len(compact) >= 24 and subject:
        return True
    return False


def _extract_vendor_records(html: str, release_url: str, allowed_domains: tuple[str, ...], max_items: int) -> list[dict]:
    parser = _ReleaseHTMLParser(release_url)
    try:
        parser.feed(html or "")
    except Exception:
        # A malformed vendor page should isolate to this vendor, not the whole run.
        return []

    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    has_h1 = any(tag == "h1" for tag, _, _ in parser.records)
    content_started = not has_h1
    current_date: str | None = None

    for tag, text, href in parser.records:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) < 5 or len(compact) > 900:
            continue

        if tag == "h1":
            content_started = True
            # Generic page titles are navigation/context, not update candidates. A
            # specific H1 such as "最新模型：Seed 2.1" may itself be decision-relevant.
            if _is_generic_page_heading(compact):
                continue
        elif not content_started:
            # First live smoke exposed nav items such as "Models & pricing" and
            # "Get API key" before the actual H1. Never turn pre-content nav into data.
            continue

        date_match = _DATE_PATTERN.search(compact)
        if date_match:
            current_date = date_match.group(0)
            # A date-only heading establishes context for following bullets/rows.
            residue = _DATE_PATTERN.sub("", compact).strip(" -–—:：|[]()")
            if not residue:
                continue

        if not _looks_like_vendor_update(tag, compact, current_date):
            continue

        candidate_url = href if href and _host_allowed(href, allowed_domains) else release_url
        key = (candidate_url, compact.casefold())
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "title": compact[:220],
                "description": compact[:700],
                "url": candidate_url,
                "published_at": date_match.group(0) if date_match else current_date,
                "html_tag": tag,
                "record_kind": "structured",
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
    # internal revision identity. Evidence resolution still uses exact primaryUrl.
    url = record_url
    if record_url.rstrip("/") == release_url.rstrip("/") or urlparse(record_url)._replace(fragment="").geturl() == urlparse(release_url)._replace(fragment="").geturl():
        url = _append_revision_identity(release_url, revision)
    return normalize_item(
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
            "vendor_record_kind": record.get("record_kind") or "structured",
        },
    )


def fetch_official_vendor_updates(limit: int, *, normalize_item, http_get, logger=None,
                                  registry=OFFICIAL_VENDOR_REGISTRY) -> list[dict]:
    """Fetch bounded official release candidates with per-vendor fault isolation."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_vendor_cap = max(1, min(8, (limit + len(registry) - 1) // max(1, len(registry))))
    buckets: dict[str, deque] = {}

    for vendor in registry:
        try:
            response = http_get(vendor["release_url"], timeout=12, headers={"User-Agent": "AI-Intelligence-Factory/Run269"})
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
                # Keep a revision-aware fallback for fault isolation, but mark it so the
                # live smoke and downstream diagnostics can distinguish reachability from
                # structured update quality. It must never masquerade as a parsed update.
                visible = re.sub(r"<[^>]+>", " ", html)
                visible = re.sub(r"\s+", " ", unescape(visible)).strip()[:700]
                if visible:
                    records = [{
                        "title": "Official page changed (structured update not resolved)",
                        "description": visible,
                        "url": vendor["release_url"],
                        "published_at": None,
                        "record_kind": "page_fallback",
                    }]
            buckets[vendor["vendor"]] = deque(
                _vendor_candidate_from_record(vendor, record, normalize_item) for record in records
            )
            if logger:
                kinds = [((row.get("sourceDetails") or {}).get("vendor_record_kind") or "") for row in buckets[vendor["vendor"]]]
                logger.info(f"[OFFICIAL VENDOR] {vendor['vendor']}: {len(kinds)} candidates kinds={kinds}")
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
    """Collect fresh title-explicit AI stories as engineer/community reaction."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_query = max(5, min(30, (limit * 2 + len(queries) - 1) // max(1, len(queries))))
    merged: dict[str, dict] = {}
    cutoff = int(datetime.now(timezone.utc).timestamp()) - HN_LOOKBACK_DAYS * 86400

    for query in queries:
        try:
            response = http_get(
                HN_ALGOLIA_ENDPOINT,
                params={
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": per_query,
                    "restrictSearchableAttributes": "title",
                    "numericFilters": f"created_at_i>{cutoff}",
                },
                timeout=10,
                headers={"User-Agent": "AI-Intelligence-Factory/Run269"},
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
        key=lambda row: (row["points"] + row["comments"], row["comments"], row["points"], row.get("created_at_i") or 0),
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
                    "lookback_days": HN_LOOKBACK_DAYS,
                },
            )
        )
    if logger:
        logger.info(f"   -> Hacker News AI reaction {len(items)} candidates from {len(queries)} title-scoped queries / {HN_LOOKBACK_DAYS}d.")
    return items
