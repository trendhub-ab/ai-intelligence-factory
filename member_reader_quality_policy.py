"""Shared customer-facing language and evidence-date policy for member surfaces.

Presentation-only. Never upgrades source freshness using page edit time, changes
a canonical decision, or requests a model. Both generated DB detail bodies
and the monthly Decision Brief must use this same policy.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REVIEW_WARNING_DAYS = 30
JST = ZoneInfo("Asia/Tokyo")

LONG_STATUS = {
    "ADOPT": "条件が合えば、使う候補に入れてよい",
    "TEST": "いきなり本番にせず、近い条件で小さく試したい",
    "WATCH": "いまは急がず、条件や成熟度の変化を見たい",
    "AVOID": "いまは選ばず、別の候補を比べたい",
}
SHORT_STATUS = {
    "ADOPT": "条件が合えば使う候補",
    "TEST": "まず小さく試す",
    "WATCH": "いまは様子を見る",
    "AVOID": "いまは選ばない",
}
DATE_PREFIX = "根拠の確認日"
REVIEW_RECHECK = "利用前に参照先の最新情報を確認してください。"


def today_jst() -> date:
    return datetime.now(JST).date()


def parse_review_date(value: Any) -> date | None:
    """Only use the recorded source-review date; reject loose/invalid values."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][^\n]+)?", raw):
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def display_date(value: Any) -> str:
    parsed = parse_review_date(value)
    return f"{parsed.year}年{parsed.month}月{parsed.day}日" if parsed else ""


def review_state(value: Any, *, as_of: date | None = None) -> str:
    """Return recorded/older/missing/invalid/future without inventing a recheck."""
    if not str(value or "").strip():
        return "missing"
    parsed = parse_review_date(value)
    if parsed is None:
        return "invalid"
    age = ((as_of or today_jst()) - parsed).days
    if age < 0:
        return "future"
    return "older" if age > REVIEW_WARNING_DAYS else "recorded"


def review_badge(value: Any, *, as_of: date | None = None) -> str:
    state = review_state(value, as_of=as_of)
    if state == "missing":
        return "未記録"
    if state in {"future", "invalid"}:
        return "確認日を要確認"
    return display_date(value) + ("（30日超）" if state == "older" else "")


def review_disclosure(value: Any, *, as_of: date | None = None) -> str:
    """Exact common prose for detail pages and month brief (same information)."""
    state = review_state(value, as_of=as_of)
    if state == "missing":
        return f"最終確認日が記録されていません。{REVIEW_RECHECK}"
    if state in {"invalid", "future"}:
        return f"記録上の確認日に不整合があります。{REVIEW_RECHECK}"
    reviewed = display_date(value)
    if state == "older":
        return f"{reviewed}に確認。30日を超えています。{REVIEW_RECHECK}"
    return f"{reviewed}に確認。以降の変更は未反映の可能性があります。{REVIEW_RECHECK}"


def source_link_label(url: str, index: int = 1) -> str:
    """Identify links by their real domain, not unverified first-party claims."""
    parsed = urlsplit(str(url or "").strip())
    host = (parsed.hostname or "").removeprefix("www.")
    if parsed.scheme != "https" or not host:
        return f"参照先 {index}"
    return f"参照先 {index}：{host}"


def status_short(value: Any) -> str:
    return SHORT_STATUS.get(str(value or "").strip().upper(), "条件を確認する")
