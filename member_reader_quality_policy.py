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


# Exact historical generated actions; custom instructions stay untouched.
ACTION_TEMPLATES = {
    "実際の業務を1つ選び、5人程度で試し、現在の方法と比べて時間・費用・使いやすさを確認してから導入範囲を決める。",
    "守りたい情報と禁止したい操作を10件程度挙げ、検証環境で防げるか確認し、既存の安全対策との役割分担を決める。",
    "代表的な業務タスクを20件程度用意し、現在の候補と同じ条件で品質・速度・費用を比較する。",
    "代表的な1つの処理を検証環境で動かし、現在の方法と速度・費用・運用負荷を比較する。",
    "実際の利用場面を1つ決め、小規模に試して効果・費用・運用負荷を確認してから導入を判断する。",
    "実際の利用者3〜5人で1週間ほど試し、使いやすさ・回答品質・費用を現在の方法と比較する。",
    "想定する事故や禁止操作を10件程度用意し、検証環境でどこまで防げるかを確認する。",
    "代表タスクを20件程度用意し、小規模テストで品質・速度・費用を現行候補と比較する。",
    "代表的な1つの処理だけを検証環境で動かし、導入前後の速度・費用・運用負荷を比較する。",
    "実際の利用場面を1つ選び、小規模テストで効果・費用・運用負荷を確認する。",
    "自社に関係する用途を1つ決め、次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。",
    "今は導入せず、次回レビュー時または大型更新時に、保守状況・価格・主要機能の変化を再確認する。",
    "新規採用は止め、同じ用途で現在も保守されている候補を2〜3件比較する。",
    "利用場面を1つ決め、必要な条件を確認してから次の判断へ進む。",
}


_GENERATED_ACTION_TAILS = ACTION_TEMPLATES | {
    "次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。",
}


def reader_action(state: dict[str, Any]) -> str:
    """Drop long duplicated context only from a recognized generated action."""
    action = " ".join(str(state.get("next_action") or "").split()).strip()
    patterns = (
        (r'^「(.+)」を想定し、(.+)$', "best_for"),
        (r'^今回の論点「(.+)」を踏まえ、(.+)$', "topic"),
    )
    for pattern, field in patterns:
        match = re.fullmatch(pattern, action)
        if not match:
            continue
        focus, tail = match.groups()
        source = " ".join(str(state.get(field) or "").split()).strip()
        fragment = re.split(r"[。！？\n]", source, maxsplit=1)[0].strip(" 、。！？")
        if len(focus) > 40 and focus == fragment and tail in _GENERATED_ACTION_TAILS:
            return tail
    return action


def reader_reason(state: dict[str, Any]) -> str:
    """Show recorded risk once, retaining any distinct rationale verbatim."""
    reason = " ".join(str(state.get("judgment_reason") or "").split()).strip()
    risk = " ".join(str(state.get("main_risk") or "").split()).strip()
    if reason == risk:
        return ""
    if not risk or not risk.endswith(("。", "！", "？")):
        return reason
    if reason.startswith(risk):
        remainder = reason[len(risk):].strip()
        if remainder == "そのため、本番導入の前に小さく試して確認します。":
            return ""
        return remainder
    if reason.endswith(risk):
        return reason[:-len(risk)].strip()
    return reason
