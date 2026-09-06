"""Run269 precision acquisition for OfficialVendor and Hacker News.

Run268 defines the business/source architecture. Run269 does not replace that
contract; it tightens live acquisition quality after real-network smoke testing
found two classes of false positive:

1. vendor navigation/documentation labels were sometimes promoted as updates;
2. HN Algolia typo tolerance could match an unrelated title (Qwen -> jQuery).

This module remains zero-model and zero-Notion. HTTP is injected so deterministic
unit tests remain hermetic while the dedicated Run269 workflow can use real public
network surfaces.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse

import business_source_acquisition as run268


SOURCE_ROLE_CONTRACT = run268.SOURCE_ROLE_CONTRACT
HN_ALGOLIA_ENDPOINT = run268.HN_ALGOLIA_ENDPOINT

# Keep the same 3 US / 8 CN business contract, but point JS-heavy/stale surfaces at
# official pages that carry the most current commercially relevant model state.
OFFICIAL_VENDOR_REGISTRY = (
    *run268.OFFICIAL_VENDOR_REGISTRY[:5],
    {
        "vendor": "ByteDance Doubao/Seed",
        "region": "CN",
        "release_url": "https://www.volcengine.com/docs/82379/2549861?lang=zh",
        "allowed_domains": ("volcengine.com",),
    },
    run268.OFFICIAL_VENDOR_REGISTRY[6],
    run268.OFFICIAL_VENDOR_REGISTRY[7],
    {
        "vendor": "MiniMax",
        "region": "CN",
        "release_url": "https://platform.minimaxi.com/docs/release-notes/models",
        "allowed_domains": ("platform.minimaxi.com", "minimaxi.com"),
    },
    run268.OFFICIAL_VENDOR_REGISTRY[9],
    {
        "vendor": "Tencent Hunyuan",
        "region": "CN",
        "release_url": "https://cloud.tencent.com/document/product/1729/97765",
        "allowed_domains": ("cloud.tencent.com", "tencent.com"),
    },
)

# Deliberately omit raw ``AI``. Exact post-filtering below is the final authority;
# Algolia's own relevance/typo behavior is never trusted as an identity check.
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
HN_LOOKBACK_DAYS = 30

_DATE_PATTERN = re.compile(
    r"(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2})",
    re.I,
)
_CHANGE_TERMS = (
    "release", "released", "introducing", "launch", "launched", "update", "updated",
    "upgrade", "upgraded", "deprecat", "sunset", "retire", "retired", "migration",
    "migrate", "discontinued", "price reduction", "price increase", "pricing change",
    "rate limit", "general availability", "now supports", "can now", "new model",
    "latest model", "发布", "正式发布", "上线", "上新", "更新", "升级", "下线", "退役",
    "降价", "涨价", "价格调整", "价格变更", "新增", "停止", "停用", "废弃", "迁移",
    "变更", "最新模型", "重磅推出",
)
_SUBJECT_TERMS = (
    "model", "gpt", "claude", "gemini", "deepseek", "qwen", "kimi", "minimax", "seed",
    "hunyuan", "ernie", "glm", "api", "sdk", "agent", "token", "context", "inference",
    "tool", "webhook", "pricing", "billing", "rate limit", "模型", "接口", "智能体", "上下文",
    "推理", "工具", "价格", "计费", "调用", "服务", "兼容", "编码",
)
_GENERIC_SNIPPETS = (
    "release notes", "platform release notes", "change log", "changelog",
    "this page documents updates", "this document", "feature update announcements",
    "model platform feature update announcements", "api docs", "get api key",
    "models & pricing", "token plan", "模型版本升级及退役机制", "产品动态", "产品公告",
    "功能更新", "新品发布", "模型发布", "模型列表", "模型更新记录",
)


def _response_text(response) -> str:
    response.raise_for_status()
    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content or "")


def _response_json(response):
    response.raise_for_status()
    return response.json()


def _host_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _is_generic(text: str) -> bool:
    low = _clean(text).casefold()
    if not low:
        return True
    if any(low == term or (term in low and len(low) <= max(100, len(term) + 45)) for term in _GENERIC_SNIPPETS):
        return True
    if low.startswith(("this page documents", "this document", "documentation index")):
        return True
    return False


def _looks_material(text: str, *, date_context: str | None = None) -> bool:
    compact = _clean(text)
    low = compact.casefold()
    if _is_generic(compact):
        return False
    has_change = any(term in low for term in _CHANGE_TERMS)
    has_subject = any(term in low for term in _SUBJECT_TERMS)
    # Strong explicit release/retirement language can stand alone when it names a
    # model family/version. Otherwise require technical/commercial subject context.
    if has_change and has_subject:
        return True
    if has_change and re.search(r"(?:[A-Za-z]{2,}[- ]?\d(?:[.\w-]*)?|\bM\d(?:[.\w-]*)?)", compact):
        return True
    if date_context and has_subject and len(compact) >= 28:
        return True
    return False


class _BlockParser(HTMLParser):
    """Collect nested reader-visible blocks without letting pre-H1 nav become data."""

    _TAGS = {"a", "h1", "h2", "h3", "h4", "li", "p", "blockquote", "tr", "td", "th", "time"}

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stack: list[dict] = []
        self.records: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self._TAGS:
            return
        attrs_dict = dict(attrs)
        href = urljoin(self.base_url, attrs_dict.get("href", "")) if tag == "a" and attrs_dict.get("href") else ""
        self.stack.append({"tag": tag, "href": href, "buf": []})

    def handle_data(self, data):
        for capture in self.stack:
            capture["buf"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] != tag:
                continue
            capture = self.stack.pop(index)
            text = _clean(" ".join(capture["buf"]))
            if text:
                self.records.append((tag, text, capture["href"]))
            return


def _tag_records(html: str, vendor: dict, max_items: int) -> list[dict]:
    parser = _BlockParser(vendor["release_url"])
    try:
        parser.feed(html or "")
    except Exception:
        return []

    has_h1 = any(tag == "h1" for tag, _, _ in parser.records)
    content_started = not has_h1
    date_context: str | None = None
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for tag, text, href in parser.records:
        if tag == "h1":
            content_started = True
            if _is_generic(text):
                continue
        elif not content_started:
            continue

        date_match = _DATE_PATTERN.search(text)
        if date_match:
            date_context = date_match.group(0)
            residue = _DATE_PATTERN.sub("", text).strip(" -–—:：|[]()")
            if not residue:
                continue

        if not _looks_material(text, date_context=date_context):
            continue
        candidate_url = href if href and _host_allowed(href, tuple(vendor["allowed_domains"])) else vendor["release_url"]
        key = (candidate_url, text.casefold())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "title": text[:220],
                "description": text[:700],
                "url": candidate_url,
                "published_at": date_match.group(0) if date_match else date_context,
                "record_kind": "structured_html",
            }
        )
        if len(rows) >= max_items:
            break
    return rows


def _decode_script_text(html: str) -> str:
    """Expose text embedded in Next/Mintlify/Tencent JSON payloads without JS execution."""
    text = unescape(html or "")
    # Decode common JSON escapes while preserving ordinary Unicode already present.
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = text.replace("\\/", "/").replace('\\"', '"')
    text = text.replace("\\n", "\n").replace("\\r", "\n").replace("\\t", " ")
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _embedded_records(html: str, vendor: dict, max_items: int) -> list[dict]:
    decoded = _decode_script_text(html)
    # Mintlify/Next payloads usually preserve escaped newlines. Tencent embeds table
    # payloads in JSON-like script data. Split aggressively but also inspect bounded
    # windows around explicit dates so relevant prose cannot be lost in one long line.
    segments = [segment.strip() for segment in re.split(r"[\n\r]+", decoded) if segment.strip()]
    for match in list(_DATE_PATTERN.finditer(decoded))[:80]:
        segments.append(decoded[max(0, match.start() - 260): min(len(decoded), match.end() + 620)])

    rows: list[dict] = []
    seen: set[str] = set()
    for segment in segments:
        compact = _clean(re.sub(r"[{}\[\]<>]+", " ", segment))
        if len(compact) < 12:
            continue
        # Extremely long script chunks are bounded around the first change term.
        if len(compact) > 900:
            low = compact.casefold()
            positions = [low.find(term) for term in _CHANGE_TERMS if low.find(term) >= 0]
            if not positions:
                continue
            pos = min(positions)
            compact = _clean(compact[max(0, pos - 220): pos + 620])
        date_match = _DATE_PATTERN.search(compact)
        if not date_match or not _looks_material(compact, date_context=date_match.group(0)):
            continue
        # Require either a model/version token or an explicit commercial lifecycle word
        # so generic site JavaScript containing words like "update" is not promoted.
        low = compact.casefold()
        if not (
            re.search(r"(?:[A-Za-z]{2,}[- ]?\d(?:[.\w-]*)?|\bM\d(?:[.\w-]*)?)", compact)
            or any(term in low for term in ("下线", "退役", "deprecat", "sunset", "retire", "migration", "价格", "pricing"))
        ):
            continue
        key = compact.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "title": compact[:220],
                "description": compact[:700],
                "url": vendor["release_url"],
                "published_at": date_match.group(0),
                "record_kind": "structured_embedded",
            }
        )
        if len(rows) >= max_items:
            break
    return rows


def _to_item(vendor: dict, record: dict, normalize_item) -> dict:
    item = run268._vendor_candidate_from_record(vendor, record, normalize_item)
    details = dict(item.get("sourceDetails") or {})
    details["vendor_record_kind"] = record.get("record_kind") or "structured_html"
    details["run269_precision"] = True
    item["sourceDetails"] = details
    return item


def _page_fallback(vendor: dict, html: str, normalize_item) -> dict | None:
    visible = _clean(re.sub(r"<[^>]+>", " ", html))[:700]
    if not visible:
        return None
    record = {
        "title": "Official page reachable; structured update unresolved",
        "description": visible,
        "url": vendor["release_url"],
        "published_at": None,
        "record_kind": "page_fallback",
    }
    return _to_item(vendor, record, normalize_item)


def fetch_official_vendor_updates(limit: int, *, normalize_item, http_get, logger=None,
                                  registry=OFFICIAL_VENDOR_REGISTRY) -> list[dict]:
    """Return high-precision official updates with vendor-level round robin."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_vendor_cap = max(1, min(6, (limit + len(registry) - 1) // max(1, len(registry))))
    buckets: dict[str, deque] = {}

    for vendor in registry:
        try:
            response = http_get(
                vendor["release_url"],
                timeout=12,
                headers={"User-Agent": "AI-Intelligence-Factory/Run269"},
            )
            final_url = str(getattr(response, "url", "") or vendor["release_url"])
            if not _host_allowed(final_url, tuple(vendor["allowed_domains"])):
                raise ValueError(f"redirected outside vendor allowlist: {final_url}")
            html = _response_text(response)
            records = _tag_records(html, vendor, per_vendor_cap)
            if len(records) < per_vendor_cap:
                embedded = _embedded_records(html, vendor, per_vendor_cap)
                existing = {(r["title"].casefold(), r.get("published_at")) for r in records}
                for record in embedded:
                    key = (record["title"].casefold(), record.get("published_at"))
                    if key not in existing:
                        records.append(record)
                        existing.add(key)
                    if len(records) >= per_vendor_cap:
                        break
            items = [_to_item(vendor, record, normalize_item) for record in records]
            if not items:
                fallback = _page_fallback(vendor, html, normalize_item)
                if fallback:
                    items = [fallback]
            buckets[vendor["vendor"]] = deque(items)
            if logger:
                kinds = [((item.get("sourceDetails") or {}).get("vendor_record_kind") or "") for item in items]
                logger.info(f"[RUN269 OFFICIAL VENDOR] {vendor['vendor']}: {len(items)} candidates kinds={kinds}")
        except Exception as exc:
            buckets[vendor["vendor"]] = deque()
            if logger:
                logger.warning(f"[RUN269 OFFICIAL VENDOR SKIP] {vendor['vendor']}: {exc}")

    result: list[dict] = []
    while len(result) < limit and any(buckets.values()):
        for vendor in registry:
            queue = buckets.get(vendor["vendor"])
            if queue:
                result.append(queue.popleft())
                if len(result) >= limit:
                    break
    return result


def _normalized_search_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def _query_matches_title(title: str, query: str) -> bool:
    needle = _normalized_search_text((query or "").strip().strip('"'))
    haystack = _normalized_search_text(title)
    if not needle or not haystack:
        return False
    # Space padding gives token-boundary behavior for short brand terms such as Qwen
    # and LLM; it also preserves exact phrase matching for quoted multi-word queries.
    return f" {needle} " in f" {haystack} "


def _hn_timestamp(created_at: str | None, created_at_i) -> str | None:
    if created_at:
        return str(created_at)
    try:
        return datetime.fromtimestamp(int(created_at_i), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def fetch_hackernews_ai_reactions(limit: int, *, normalize_item, http_get, logger=None,
                                  queries=HN_AI_QUERIES) -> list[dict]:
    """Collect fresh title-explicit AI stories; reject Algolia typo false matches."""
    limit = max(0, int(limit or 0))
    if limit <= 0:
        return []
    per_query = max(6, min(35, (limit * 3 + len(queries) - 1) // max(1, len(queries))))
    cutoff = int(datetime.now(timezone.utc).timestamp()) - HN_LOOKBACK_DAYS * 86400
    merged: dict[str, dict] = {}

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
                if not object_id or not title or not _query_matches_title(title, query):
                    continue
                points = max(0, int(hit.get("points") or 0))
                comments = max(0, int(hit.get("num_comments") or 0))
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
                previous = merged.get(object_id)
                if previous is None or (points + comments) > (previous["points"] + previous["comments"]):
                    merged[object_id] = candidate
        except Exception as exc:
            if logger:
                logger.warning(f"[RUN269 HN QUERY SKIP] query={query!r}: {exc}")

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
                    "run269_precision": True,
                },
            )
        )
    if logger:
        logger.info(
            f"   -> Run269 HN reaction {len(items)} candidates from {len(queries)} exact-title queries / {HN_LOOKBACK_DAYS}d."
        )
    return items
