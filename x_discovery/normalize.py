from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from .models import DiscoverySignal
from .url_resolution import extract_external_urls


def _first(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return None


def _handle(record: Mapping[str, Any]) -> str:
    direct = _first(
        record,
        "author_handle",
        "authorHandle",
        "authorUserName",
        "username",
        "userName",
        "screen_name",
        "handle",
    )
    if direct:
        return str(direct).lstrip("@")
    author = record.get("author") or record.get("user")
    if isinstance(author, Mapping):
        nested = _first(author, "username", "userName", "screen_name", "handle", "name")
        if nested:
            return str(nested).lstrip("@")
    if isinstance(author, str):
        return author.lstrip("@")
    return "unknown"


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _engagement(record: Mapping[str, Any]) -> Dict[str, int]:
    public_metrics = record.get("public_metrics")
    metrics = public_metrics if isinstance(public_metrics, Mapping) else {}
    return {
        "likes": _int(
            _first(record, "like_count", "likeCount", "likes", "favorite_count")
            or metrics.get("like_count")
        ),
        "reposts": _int(
            _first(record, "retweet_count", "retweetCount", "repost_count", "repostCount", "retweets")
            or metrics.get("retweet_count")
        ),
        "replies": _int(
            _first(record, "reply_count", "replyCount", "replies")
            or metrics.get("reply_count")
        ),
        "quotes": _int(
            _first(record, "quote_count", "quoteCount", "quotes")
            or metrics.get("quote_count")
        ),
        "views": _int(
            _first(record, "view_count", "viewCount", "views", "impressions")
            or metrics.get("impression_count")
        ),
        "bookmarks": _int(
            _first(record, "bookmark_count", "bookmarkCount", "bookmarks")
            or metrics.get("bookmark_count")
        ),
    }


def normalize_post(
    record: Mapping[str, Any],
    *,
    provider: str,
    discovered_at: Optional[str] = None,
) -> DiscoverySignal:
    text = str(_first(record, "text", "full_text", "fullText", "content") or "").strip()
    handle = _handle(record)
    post_url = str(_first(record, "post_url", "tweet_url", "twitterUrl", "url") or "").strip()
    post_id_raw = _first(record, "post_id", "tweet_id", "id_str", "id")
    if post_id_raw is None:
        seed = "|".join((post_url, handle, text))
        post_id = "derived-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    else:
        post_id = str(post_id_raw)

    posted_at_raw = _first(
        record,
        "posted_at",
        "created_at",
        "createdAtIso",
        "createdAt",
        "timestamp",
        "date",
    )
    posted_at = str(posted_at_raw) if posted_at_raw is not None else None
    now = discovered_at or datetime.now(timezone.utc).isoformat()

    return DiscoverySignal(
        source_platform="x",
        post_id=post_id,
        author_handle=handle,
        post_url=post_url,
        posted_at=posted_at,
        text=text,
        external_urls=extract_external_urls(record, text),
        engagement_snapshot=_engagement(record),
        discovered_at=now,
        provider=provider,
    )
