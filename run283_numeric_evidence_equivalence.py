"""Run283: conservative cross-language numeric evidence equivalence.

Production finding from Run282:
- Anthropic's primary source explicitly says cache reads cost ``0.1x`` input price, while
  the Japanese article naturally rendered that as ``10分の1``.
- The same source says prompt cache expires after ``an hour`` on a subscription, while the
  article rendered that as ``1時間``.

The base numeric validator intentionally does not perform semantic conversion. This overlay
removes only ``unsupported numeric claim`` failures when exact quantity equivalence is proven
in primary-source text *and* the local semantic context matches. It does not weaken numeric
condition mismatches, inferred numbers, vague quantities, actor checks, hype checks, or any
other Fact Gate.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_INSTALLED_ATTR = "_run283_numeric_evidence_equivalence_installed"
_UNSUPPORTED_PREFIX = "unsupported numeric claim: "

_DOMAIN_PATTERNS = {
    "pricing": re.compile(
        r"(?:価格|料金|費用|コスト|課金|billing|billed|price|pricing|cost|input\s+token)",
        re.I,
    ),
    "performance": re.compile(
        r"(?:性能|速度|高速|レイテンシ|処理速度|performance|faster|speed(?:up)?|latency|throughput)",
        re.I,
    ),
}
_TIME_PURPOSE_PATTERNS = {
    "cache_expiry": re.compile(
        r"(?:キャッシュ|cache).{0,100}(?:失効|期限|ttl|expire|expires|expiration|duration)|"
        r"(?:失効|期限|ttl|expire|expires|expiration|duration).{0,100}(?:キャッシュ|cache)",
        re.I | re.S,
    ),
    "runtime": re.compile(
        r"(?:実行時間|処理時間|所要時間|runtime|execution\s+time|processing\s+time)",
        re.I,
    ),
    "timeout": re.compile(r"(?:タイムアウト|timeout)", re.I),
    "session": re.compile(r"(?:セッション|session)", re.I),
    "retention": re.compile(r"(?:保持期間|保存期間|retention)", re.I),
}
_TOPIC_PATTERNS = {
    "cache": re.compile(r"(?:プロンプトキャッシュ|キャッシュ|prompt\s+cache|cache)", re.I),
    "subscription": re.compile(r"(?:サブスクリプション|subscription)", re.I),
    "api": re.compile(r"(?:APIキー|API\s*key|api)", re.I),
}


def _window(text: str, start: int, end: int, left: int = 140, right: int = 180) -> str:
    body = text or ""
    return body[max(0, start - left): min(len(body), end + right)]


def _claim_windows(draft: str, token: str) -> list[str]:
    if not token:
        return []
    return [
        _window(draft, match.start(), match.end())
        for match in re.finditer(re.escape(token), draft or "", re.I)
    ]


def _ratio_value_from_japanese_fraction(token: str) -> Decimal | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*分の\s*(\d+(?:\.\d+)?)\s*", token or "")
    if not match:
        return None
    try:
        denominator = Decimal(match.group(1))
        numerator = Decimal(match.group(2))
    except InvalidOperation:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def _decimal_variants(value: Decimal) -> tuple[str, ...]:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return (normalized or "0",)


def _ratio_evidence_windows(source_context: str, ratio: Decimal) -> list[str]:
    windows: list[str] = []
    for value in _decimal_variants(ratio):
        patterns = (
            rf"(?<![\d.]){re.escape(value)}\s*(?:x|×|倍)(?![A-Za-z0-9_.])",
            rf"(?<![\d.]){re.escape(value)}\s+(?:times?)(?![A-Za-z0-9_])",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, source_context or "", re.I):
                windows.append(_window(source_context, match.start(), match.end(), 220, 260))
    return windows


def _one_unit_evidence_windows(source_context: str, token: str) -> list[str]:
    match = re.fullmatch(r"\s*1\s*(時間|分|日|週間|週|ヶ月|か月)\s*", token or "")
    if not match:
        return []
    english = {
        "時間": r"hours?",
        "分": r"minutes?",
        "日": r"days?",
        "週間": r"weeks?",
        "週": r"weeks?",
        "ヶ月": r"months?",
        "か月": r"months?",
    }[match.group(1)]
    pattern = rf"\b(?:1|one|an|a)(?:\s+|-){english}\b"
    return [
        _window(source_context, evidence_match.start(), evidence_match.end(), 220, 260)
        for evidence_match in re.finditer(pattern, source_context or "", re.I)
    ]


def _tags(text: str, patterns: dict[str, re.Pattern]) -> set[str]:
    return {name for name, pattern in patterns.items() if pattern.search(text or "")}


def _semantic_context_compatible(token: str, claim_window: str, evidence_window: str) -> bool:
    """Require quantity equivalence to refer to the same local semantic purpose.

    A source may legitimately contain several ``0.1x`` or ``one hour`` values. Quantity alone
    must never allow a pricing value to legalize a speed claim, or a cache TTL to legalize a
    runtime claim. Specific domains/purposes therefore take precedence over broad topic tags.
    """
    if _ratio_value_from_japanese_fraction(token) is not None:
        claim_domains = _tags(claim_window, _DOMAIN_PATTERNS)
        evidence_domains = _tags(evidence_window, _DOMAIN_PATTERNS)
        if claim_domains or evidence_domains:
            return bool(claim_domains & evidence_domains)
        return bool(_tags(claim_window, _TOPIC_PATTERNS) & _tags(evidence_window, _TOPIC_PATTERNS))

    if re.fullmatch(r"\s*1\s*(時間|分|日|週間|週|ヶ月|か月)\s*", token or ""):
        claim_purposes = _tags(claim_window, _TIME_PURPOSE_PATTERNS)
        evidence_purposes = _tags(evidence_window, _TIME_PURPOSE_PATTERNS)
        if claim_purposes or evidence_purposes:
            return bool(claim_purposes & evidence_purposes)
        return bool(_tags(claim_window, _TOPIC_PATTERNS) & _tags(evidence_window, _TOPIC_PATTERNS))

    return False


def _equivalent_numeric_claim_supported(
    token: str,
    draft: str,
    source_context: str,
    condition_compatible,
) -> bool:
    claim_windows = _claim_windows(draft, token)
    if not claim_windows:
        return False

    evidence_windows: list[str] = []
    ratio = _ratio_value_from_japanese_fraction(token)
    if ratio is not None:
        evidence_windows.extend(_ratio_evidence_windows(source_context, ratio))
    evidence_windows.extend(_one_unit_evidence_windows(source_context, token))
    if not evidence_windows:
        return False

    return any(
        condition_compatible(claim_window, evidence_window)
        and _semantic_context_compatible(token, claim_window, evidence_window)
        for claim_window in claim_windows
        for evidence_window in evidence_windows
    )


def filter_numeric_false_positives(
    failures: list[str],
    draft: str,
    source_context: str,
    *,
    condition_compatible,
) -> list[str]:
    filtered: list[str] = []
    for failure in failures or []:
        text = str(failure or "")
        if not text.startswith(_UNSUPPORTED_PREFIX):
            filtered.append(failure)
            continue
        token = text[len(_UNSUPPORTED_PREFIX):].strip()
        if _equivalent_numeric_claim_supported(
            token,
            draft,
            source_context,
            condition_compatible,
        ):
            continue
        filtered.append(failure)
    return filtered


def install(pipeline_module: Any) -> Any:
    """Wrap only numeric unsupported-claim validation; all other Fact Gate behavior stays base."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original = pipeline_module._find_unsupported_numeric_claims
    condition_compatible = pipeline_module._numeric_condition_compatible

    def _find_unsupported_numeric_claims_with_equivalence(
        draft: str,
        source_context: str,
        evidence_metadata: dict | None = None,
    ) -> list[str]:
        failures = original(draft, source_context, evidence_metadata)
        return filter_numeric_false_positives(
            failures,
            draft,
            source_context,
            condition_compatible=condition_compatible,
        )

    pipeline_module._find_unsupported_numeric_claims = _find_unsupported_numeric_claims_with_equivalence
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
