"""Evidence-bounded publication safety for Local Skills.

This layer is deterministic and provider-free. It removes reader-facing numeric
claims that are not present in the actual primary-source verification context.
It never edits Decision, Score, source identity, URLs, or Gate policy.

The goal is deliberately conservative: exact/semantically-equivalent numeric
lexemes may survive; derived conversions or newly introduced amounts must not.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

EVIDENCE_BOUNDARY_VERSION = "stage8-v1"

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

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![A-Za-z0-9])"
)

# Only claims with an explicit sensitive unit are filtered here. Bare version
# numbers and identifiers are left to the existing Fact/Publication gates.
_SENSITIVE_NUMERIC_RE = re.compile(
    r"(?P<prefix>(?:約|およそ|概ね|ほぼ)?\s*[¥￥$€£]?\s*)"
    r"(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<unit>"
    r"米ドル|ドル|円|JPY|USD|EUR|GBP|"
    r"％|%|ミリ秒|ms|秒|分|時間|"
    r"倍|[xX]|TB|GB|MB|KB|"
    r"トークン|tokens?"
    r")",
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


def _evidence_number_keys(evidence_context: str) -> set[str]:
    return {_number_key(match.group(1)) for match in _NUMBER_RE.finditer(str(evidence_context or ""))}


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


def _sanitize_field(field: str, value: str, evidence_numbers: set[str]) -> tuple[str, list[str]]:
    text = _clean(value)
    if not text:
        return text, []

    removed: list[str] = []
    matches = list(_SENSITIVE_NUMERIC_RE.finditer(text))
    for match in reversed(matches):
        number = _number_key(match.group("number"))
        if number in evidence_numbers:
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
    """Return a publication snapshot bounded by actual verification evidence.

    This function does not treat the Structured Record itself as proof for a
    derived numeric value. Production should pass its primary-source verification
    context. Offline experiments may explicitly pass the stored evidence surface.
    """
    out = deepcopy(dict(snapshot))
    evidence_numbers = _evidence_number_keys(evidence_context)
    removed_rows: list[dict[str, str]] = []

    for field in PUBLICATION_FIELDS:
        sanitized, removed = _sanitize_field(field, out.get(field, ""), evidence_numbers)
        out[field] = sanitized
        for claim in removed:
            removed_rows.append({"field": field, "claim": claim})

    return out, {
        "version": EVIDENCE_BOUNDARY_VERSION,
        "removed_unsupported_numeric_claims": removed_rows,
        "removed_count": len(removed_rows),
    }
