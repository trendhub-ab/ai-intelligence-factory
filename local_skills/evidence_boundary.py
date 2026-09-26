"""Evidence-bounded publication safety for Local Skills.

Deterministic and provider-free. Reader-facing sensitive numeric claims survive
only when the primary-source verification context contains the same numeric value
with a compatible unit class. This prevents a derived currency conversion from
being treated as sourced merely because the same number appears elsewhere.

Decision, Score, source identity, URLs and Gate policy are never edited here.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

EVIDENCE_BOUNDARY_VERSION = "stage8-v2"

PUBLICATION_FIELDS = (
    "source_summary",
    "what",
    "why_important",
    "decision_reason",
    "action",
    "primary_risk",
    "best_for",
    "avoid_for",
)

_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

# Reader-facing claims. A prefix currency symbol is enough to make a numeric
# expression sensitive even when no trailing currency code is present.
_SENSITIVE_NUMERIC_RE = re.compile(
    rf"(?P<qualifier>(?:約|およそ|概ね|ほぼ)?\s*)"
    rf"(?P<symbol>[¥￥$€£]?)\s*"
    rf"(?P<number>{_NUMBER})\s*"
    r"(?P<unit>"
    r"米ドル|ドル|円|JPY|USD|EUR|GBP|"
    r"％|%|ミリ秒|ms|秒|分|時間|"
    r"倍|[xX]|TB|GB|MB|KB|"
    r"トークン|tokens?"
    r")?",
    re.I,
)

# Evidence may be English or Japanese. Bare numbers are intentionally not
# sufficient to support a reader-facing amount/duration/multiplier claim.
_EVIDENCE_NUMERIC_RE = re.compile(
    rf"(?P<qualifier>(?:about|approximately|approx\.?|約|およそ|概ね|ほぼ)?\s*)"
    rf"(?P<symbol>[¥￥$€£]?)\s*"
    rf"(?P<number>{_NUMBER})\s*"
    r"(?P<unit>"
    r"米ドル|ドル|円|JPY|USD|EUR|GBP|"
    r"％|%|percent|"
    r"ミリ秒|milliseconds?|msecs?|ms|"
    r"秒|seconds?|secs?|"
    r"分|minutes?|mins?|"
    r"時間|hours?|hrs?|"
    r"倍|[xX]|times?|"
    r"TB|GB|MB|KB|"
    r"トークン|tokens?"
    r")?",
    re.I,
)

_FIELD_FALLBACKS = {
    "source_summary": "一次情報で確認できる範囲だけを、判断材料として整理します。",
    "what": "一次情報で確認できる内容だけを記事に残します。",
    "why_important": "重要性は一次情報で確認できる範囲を越えて断定せず、検証材料として扱います。",
    "decision_reason": "判断理由は、一次情報で確認できる事実と未確認部分を分けて扱います。",
    "action": "一次情報で確認できる範囲から、小さな検証で追加確認します。",
    "primary_risk": "一次情報の対象範囲を越えて一般化しないことが重要です。",
    "best_for": "一次情報の範囲を守って限定検証できるチーム。",
    "avoid_for": "未確認の数値や効果を前提に本番適用したいチーム。",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _number_key(value: str) -> str:
    raw = str(value or "").replace(",", "")
    try:
        return format(Decimal(raw).normalize(), "f")
    except (InvalidOperation, ValueError):
        return raw


def _unit_class(symbol: str, unit: str) -> str:
    symbol = str(symbol or "")
    raw = str(unit or "").strip().casefold()

    if symbol in {"¥", "￥"} or raw in {"円", "jpy"}:
        return "currency:jpy"
    if symbol == "$" or raw in {"米ドル", "ドル", "usd"}:
        return "currency:usd"
    if symbol == "€" or raw == "eur":
        return "currency:eur"
    if symbol == "£" or raw == "gbp":
        return "currency:gbp"

    if raw in {"％", "%", "percent"}:
        return "percent"
    if raw in {"ミリ秒", "millisecond", "milliseconds", "msec", "msecs", "ms"}:
        return "time:ms"
    if raw in {"秒", "second", "seconds", "sec", "secs"}:
        return "time:s"
    if raw in {"分", "minute", "minutes", "min", "mins"}:
        return "time:min"
    if raw in {"時間", "hour", "hours", "hr", "hrs"}:
        return "time:h"
    if raw in {"倍", "x", "time", "times"}:
        return "multiplier"
    if raw in {"tb", "gb", "mb", "kb"}:
        return f"storage:{raw}"
    if raw in {"トークン", "token", "tokens"}:
        return "tokens"
    return ""


def _evidence_claim_keys(evidence_context: str) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for match in _EVIDENCE_NUMERIC_RE.finditer(str(evidence_context or "")):
        unit_class = _unit_class(match.group("symbol"), match.group("unit"))
        if not unit_class:
            continue
        keys.add((_number_key(match.group("number")), unit_class))
    return keys


def _remove_span_with_delimiter(text: str, start: int, end: int) -> str:
    """Remove one unsupported numeric expression without leaving broken separators."""
    left = start
    right = end
    while left > 0 and text[left - 1] in " \t":
        left -= 1
    if left > 0 and text[left - 1] in "・/／、,，":
        left -= 1
    while right < len(text) and text[right] in " \t":
        right += 1
    out = text[:left] + text[right:]
    out = re.sub(r"・{2,}", "・", out)
    out = re.sub(r"([、,，])\s*([、,，])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def _sanitize_field(
    field: str,
    value: str,
    evidence_claims: set[tuple[str, str]],
) -> tuple[str, list[str]]:
    text = _clean(value)
    if not text:
        return text, []

    removed: list[str] = []
    matches = list(_SENSITIVE_NUMERIC_RE.finditer(text))
    for match in reversed(matches):
        unit_class = _unit_class(match.group("symbol"), match.group("unit"))
        # Ignore bare version/identifier numbers; existing Gates own those.
        if not unit_class:
            continue
        claim_key = (_number_key(match.group("number")), unit_class)
        if claim_key in evidence_claims:
            continue
        removed.append(match.group(0).strip())
        text = _remove_span_with_delimiter(text, match.start(), match.end())

    text = _clean(text)
    if removed and not text:
        text = _FIELD_FALLBACKS[field]
    return text, list(reversed(removed))


def apply_evidence_boundary(
    snapshot: Mapping[str, Any],
    evidence_context: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a publication snapshot bounded by actual verification evidence."""
    out = deepcopy(dict(snapshot))
    evidence_claims = _evidence_claim_keys(evidence_context)
    removed_rows: list[dict[str, str]] = []

    for field in PUBLICATION_FIELDS:
        sanitized, removed = _sanitize_field(field, out.get(field, ""), evidence_claims)
        out[field] = sanitized
        for claim in removed:
            removed_rows.append({"field": field, "claim": claim})

    return out, {
        "version": EVIDENCE_BOUNDARY_VERSION,
        "removed_unsupported_numeric_claims": removed_rows,
        "removed_count": len(removed_rows),
    }
