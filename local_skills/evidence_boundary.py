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

EVIDENCE_BOUNDARY_VERSION = "stage9-v4"

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

_VAGUE_TEMPORAL_RE = re.compile(r"半年|数日|数週間|数週|数ヶ月|数か月|数月|数年")
_VAGUE_TEMPORAL_EVIDENCE = {
    "半年": r"(?:half\s+(?:a\s+)?year|six\s+months|6\s+months)",
    "数日": r"(?:several|a\s+few)\s+days",
    "数週間": r"(?:several|a\s+few)\s+weeks",
    "数週": r"(?:several|a\s+few)\s+weeks",
    "数ヶ月": r"(?:coming|next|several|a\s+few)\s+months",
    "数か月": r"(?:coming|next|several|a\s+few)\s+months",
    "数月": r"(?:several|a\s+few)\s+months",
    "数年": r"(?:several|a\s+few)\s+years",
}

_STAGE_SINGLE_GPU_TRAINING_EVIDENCE_RE = re.compile(
    r"(?:single\s+gpu|one\s+gpu).{0,180}(?:simulat|train|learn)|"
    r"(?:simulat|train|learn).{0,180}(?:single\s+gpu|one\s+gpu)",
    re.I | re.S,
)
_STAGE_HARDWARE_DEPLOYMENT_EVIDENCE_RE = re.compile(
    r"(?:hardware\s+deployment|real\s+(?:unitree\s+)?go2|real[- ]world|"
    r"zero[- ]shot.{0,100}(?:real|hardware))",
    re.I | re.S,
)
_STAGE_DISTILLATION_EVIDENCE_RE = re.compile(
    r"(?:distilled\s+policy|distill(?:ed|ation).{0,100}(?:policy|deployment|transfer))",
    re.I | re.S,
)
_STAGE_ZERO_SHOT_EVIDENCE_RE = re.compile(
    r"zero[- ]shot.{0,120}(?:real|hardware|unitree|go2|transfer|deployment)",
    re.I | re.S,
)
_STAGE_FUSED_SENTENCE_RE = re.compile(
    r"(?:(?:1台|単一|single|one).{0,10}GPU|GPU.{0,10}(?:1台|single|one))"
    r"[^。！？!?\n]{0,120}(?:実機|実ロボット|real\s+(?:robot|go2)|hardware)"
    r"[^。！？!?\n]{0,80}|"
    r"(?:実機|実ロボット|real\s+(?:robot|go2)|hardware)"
    r"[^。！？!?\n]{0,120}(?:(?:1台|単一|single|one).{0,10}GPU|GPU.{0,10}(?:1台|single|one))",
    re.I,
)


def _repair_stage_boundary(value: str, evidence_context: str) -> tuple[str, int]:
    """Restore a proven training/deployment boundary before publication."""
    text = _clean(value)
    evidence = str(evidence_context or "")
    if not text:
        return text, 0
    if not _STAGE_SINGLE_GPU_TRAINING_EVIDENCE_RE.search(evidence):
        return text, 0
    if not _STAGE_HARDWARE_DEPLOYMENT_EVIDENCE_RE.search(evidence):
        return text, 0

    replacement = "一次情報では、単一GPUはシミュレーション上の学習条件として示されています。"
    if _STAGE_DISTILLATION_EVIDENCE_RE.search(evidence):
        if _STAGE_ZERO_SHOT_EVIDENCE_RE.search(evidence):
            replacement += "実機へのゼロショット転移は、蒸留したポリシーを用いる別工程として報告されています。"
        else:
            replacement += "実機展開は、蒸留したポリシーを用いる別工程として報告されています。"
    elif _STAGE_ZERO_SHOT_EVIDENCE_RE.search(evidence):
        replacement += "実機へのゼロショット転移は、学習とは別工程として報告されています。"
    else:
        replacement += "実機展開は、学習とは別工程として報告されています。"

    repaired = 0
    pieces = re.split(r"(?<=[。！？!?])", text)
    out: list[str] = []
    for piece in pieces:
        if _STAGE_FUSED_SENTENCE_RE.search(piece):
            out.append(replacement)
            repaired += 1
        else:
            out.append(piece)
    return _clean("".join(out)), repaired



def _vague_temporal_supported(token: str, evidence_context: str) -> bool:
    evidence = str(evidence_context or "")
    if token in evidence:
        return True
    pattern = _VAGUE_TEMPORAL_EVIDENCE.get(token)
    return bool(pattern and re.search(pattern, evidence, re.I))


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




def _fact_numeric_normalize(text: str) -> str:
    """Mirror Fact Gate numeric surface normalization without changing Gate policy."""
    value = __import__("unicodedata").normalize("NFKC", str(text or "")).lower()
    value = re.sub(r"(\\d+)\\s*分の\\s*(\\d+)", lambda m: f"{m.group(2)}/{m.group(1)}", value)
    value = value.replace("ミリ秒", "ms").replace("秒", "s")
    value = re.sub(r"\\bseconds?\\b|\\bsec\\b", "s", value)
    value = value.replace("トークン", "tokens").replace("リクエスト", "requests")
    value = re.sub(r"\\btoken\\b", "tokens", value)
    value = re.sub(r"\\brequest\\b", "requests", value)
    value = re.sub(r"(?<=\\d)分(?!\\s*(?:野|割|布|類|岐|析))", "minutes", value)
    value = re.sub(r"(?<=\\d)日", "days", value)
    value = value.replace("時間", "hours").replace("週間", "weeks").replace("週", "weeks")
    value = re.sub(r"\\bminutes?\\b|\\bmins?\\b", "minutes", value)
    value = re.sub(r"\\bdays?\\b", "days", value)
    value = value.replace("ヶ月", "months").replace("か月", "months")
    value = re.sub(r"\\bhours?\\b", "hours", value)
    value = re.sub(r"\\bweeks?\\b", "weeks", value)
    value = re.sub(r"\\bmonths?\\b", "months", value)
    value = value.replace("ドル", "usd")
    value = re.sub(r"\\busd\\b", "usd", value)
    value = value.replace("×", "x").replace("倍", "x")
    value = value.replace("パーセント", "%")
    value = re.sub(r"\\bpercent(?:age)?\\b", "%", value)
    value = value.replace("〜", "-").replace("～", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    value = re.sub(r"\\bto\\b", "-", value)
    value = re.sub(r"(?<=\\d)-(?=(?:hours|minutes|days|weeks|months|ms|s|tokens|requests)\\b)", "", value)
    value = re.sub(r"%(?=-\\d)", "", value)
    value = value.replace("約", "")
    return re.sub(r"[\\s,，]", "", value)


def _evidence_claim_keys(evidence_context: str) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for match in _EVIDENCE_NUMERIC_RE.finditer(str(evidence_context or "")):
        unit_class = _unit_class(match.group("symbol"), match.group("unit"))
        if not unit_class:
            continue
        keys.add((_number_key(match.group("number")), unit_class))
    return keys


def _repair_numeric_deletion_residue(text: str) -> str:
    """Repair grammar fragments created only by deleting unsupported numeric spans.

    This never restores or invents a number. It removes dangling comparative particles
    such as 「からへ」 and normalizes possessive fragments such as 「上でからへの高速化」
    that can remain after both endpoints of a comparison are evidence-bounded away.
    """
    value = str(text or "")
    value = re.sub(r"上で\s*から\s*へ\s*の", "上での", value)
    value = re.sub(r"から\s*へ(?=(?:約|およそ|概ね|ほぼ)?\s*\d|\s*(?:高速|改善|短縮|増加|減少|低下|向上|変化))", "", value)
    value = re.sub(r"から\s*へ\s*の", "の", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


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

    text = _repair_numeric_deletion_residue(_clean(text))
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
    fact_normalized_evidence = _fact_numeric_normalize(evidence_context)
    removed_rows: list[dict[str, str]] = []
    repaired_stage_fusion_rows: list[dict[str, str]] = []

    for field in PUBLICATION_FIELDS:
        raw_value = out.get(field, "")
        stage_repaired, stage_repair_count = _repair_stage_boundary(
            _clean(raw_value), evidence_context
        )
        if stage_repair_count:
            repaired_stage_fusion_rows.append({
                "field": field,
                "repair": "training_and_hardware_deployment_separated",
            })
        sanitized, removed = _sanitize_field(field, stage_repaired, evidence_claims)
        # Unit-class compatibility is necessary but not sufficient: Fact Gate
        # intentionally does not equate every semantically similar currency
        # notation (for example "$100" and "100ドル"). Fail closed here so the
        # deterministic compiler cannot emit a token the unchanged Fact Gate
        # will reject.
        for match in reversed(list(_SENSITIVE_NUMERIC_RE.finditer(sanitized))):
            unit_class = _unit_class(match.group("symbol"), match.group("unit"))
            if not unit_class:
                continue
            token = match.group(0).strip()
            if _fact_numeric_normalize(token) not in fact_normalized_evidence:
                removed.append(token)
                sanitized = _remove_span_with_delimiter(
                    sanitized, match.start(), match.end()
                )
        sanitized = _repair_numeric_deletion_residue(_clean(sanitized))

        # Fact Gate also treats vague temporal quantities as factual claims.
        # If Deep Dive introduces one that primary-source evidence does not support,
        # fail closed before publication by replacing only that derived field with
        # its deterministic evidence-bounded fallback. This preserves the Gate
        # threshold while preventing malformed prose from token-level deletion.
        for vague_match in _VAGUE_TEMPORAL_RE.finditer(sanitized):
            token = vague_match.group(0)
            if _vague_temporal_supported(token, evidence_context):
                continue
            removed.append(token)
            sanitized = _FIELD_FALLBACKS[field]
            break

        sanitized = _repair_numeric_deletion_residue(_clean(sanitized))
        if removed and not sanitized:
            sanitized = _FIELD_FALLBACKS[field]
        out[field] = sanitized
        for claim in removed:
            removed_rows.append({"field": field, "claim": claim})

    return out, {
        "version": EVIDENCE_BOUNDARY_VERSION,
        "removed_unsupported_numeric_claims": removed_rows,
        "removed_count": len(removed_rows),
        "repaired_stage_fusion": repaired_stage_fusion_rows,
        "repaired_stage_fusion_count": len(repaired_stage_fusion_rows),
    }
