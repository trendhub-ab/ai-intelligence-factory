"""Run283: conservative cross-language numeric evidence equivalence.

Production finding from Run282:
- Anthropic's primary source explicitly says cache reads cost ``0.1x`` input price, while
  the Japanese article naturally rendered that as ``10分の1``.
- The same source says prompt cache expires after ``an hour`` on a subscription, while the
  article rendered that as ``1時間``.

The base numeric validator intentionally does not perform semantic conversion.  This overlay
removes only those *unsupported numeric claim* failures when the exact mathematical/time
quantity can be proven in the primary-source text and nearby claim/evidence conditions remain
compatible.  It does not weaken condition mismatches, inferred numbers, vague quantities,
actor checks, hype checks, or any other Fact Gate.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_INSTALLED_ATTR = "_run283_numeric_evidence_equivalence_installed"
_UNSUPPORTED_PREFIX = "unsupported numeric claim: "


def _window(text: str, start: int, end: int, left: int = 140, right: int = 180) -> str:
    body = text or ""
    return body[max(0, start - left): min(len(body), end + right)]


def _claim_windows(draft: str, token: str) -> list[str]:
    if not token:
        return []
    return [_window(draft, match.start(), match.end()) for match in re.finditer(re.escape(token), draft or "", re.I)]


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
    unit = match.group(1)
    english = {
        "時間": r"hours?",
        "分": r"minutes?",
        "日": r"days?",
        "週間": r"weeks?",
        "週": r"weeks?",
        "ヶ月": r"months?",
        "か月": r"months?",
    }[unit]
    pattern = rf"\b(?:1|one|an?|a)\s+{english}\b"
    return [
        _window(source_context, match.start(), match.end(), 220, 260)
        for match in re.finditer(pattern, source_context or "", re.I)
    ]


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

    # Require at least one claim occurrence to be compatible with at least one exact
    # primary-source occurrence.  This preserves the base validator's fail-closed
    # hardware/dataset/metric condition protection.
    return any(
        condition_compatible(claim_window, evidence_window)
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
        if _equivalent_numeric_claim_supported(token, draft, source_context, condition_compatible):
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
