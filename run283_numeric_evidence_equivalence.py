"""Run283/350: conservative Fact precision for numeric equivalence and ROI evaluation intent.

Run283 production finding:
- Anthropic's primary source explicitly says cache reads cost ``0.1x`` input price, while
  the Japanese article naturally rendered that as ``10分の1``.
- The same source says prompt cache expires after ``an hour`` on a subscription, while the
  article rendered that as ``1時間``.

Run350 real-article finding:
- Run38 DeepSeek was Fact-blocked because ``自社にとって投資対効果が見合うかを見極めて
  いきましょう`` contains the term 投資対効果, even though it proposes measuring/evaluating
  ROI during a bounded trial and does not assert any ROI result.

This overlay removes only proven false positives. It never weakens numeric-condition mismatches,
inferred numbers, vague quantities, actor checks, hype checks, or positive/mixed ROI outcome
claims. It adds no provider, network, or persistence call.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_INSTALLED_ATTR = "_run283_numeric_evidence_equivalence_installed"
_UNSUPPORTED_PREFIX = "unsupported numeric claim: "
ROI_OUTCOME_FAILURE = "unsupported outcome extrapolation: ROI/financial outcome not measured by evidence"

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

# Python's Unicode \b treats Japanese characters as word characters, so ``ROIが`` does not
# satisfy ``\bROI\b``. Use ASCII-only boundaries so mixed Japanese/Latin prose is covered.
_ROI_TERM_RE = re.compile(r"(?<![A-Za-z0-9])ROI(?![A-Za-z0-9])|投資対効果|投資の成果|return on investment", re.I)
_ROI_EVALUATION_INTENT_RE = re.compile(
    r"(?:"
    r"(?:ROI|投資対効果|投資の成果).{0,36}(?:測|計測|測定|確認|検証|評価|比較|見極|判断|算出|試算|確かめ|チェック)|"
    r"(?:測|計測|測定|確認|検証|評価|比較|見極|判断|算出|試算|確かめ|チェック).{0,36}(?:ROI|投資対効果|投資の成果)|"
    r"投資対効果が見合うか|ROIが見合うか|"
    r"return on investment.{0,36}(?:measure|evaluate|assess|check|estimate|calculate|validate)"
    r")",
    re.I,
)
_ROI_OUTCOME_ASSERTION_RE = re.compile(
    r"(?:"
    r"(?:ROI|投資対効果|投資の成果).{0,36}(?:高い|低い|良い|悪い|優れる|改善|向上|増加|上がる|下がる|確実|保証|十分|大きい|小さい|見合う(?:。|です|といえる|と言える))|"
    r"(?:高い|低い|良い|悪い|優れる|改善|向上|増加|確実|保証).{0,36}(?:ROI|投資対効果|投資の成果)|"
    r"(?:ROI|投資対効果|投資の成果).{0,24}(?:\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*[倍x×]|黒字|赤字|回収|利益|収益)|"
    r"return on investment.{0,36}(?:high|low|better|improv|increase|decrease|guarantee|positive|negative|profitable)"
    r")",
    re.I,
)


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
    """Require quantity equivalence to refer to the same local semantic purpose."""
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
            condition_compatible=condition_compatible,
        ):
            continue
        filtered.append(failure)
    return filtered


def _sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"(?<=[。！？!?])|\n+", str(text or ""))
        if part and part.strip()
    ]


def roi_sentences_are_evaluation_intent_only(text: str) -> bool:
    """True only when every ROI-bearing sentence is an instruction to evaluate, not an outcome.

    Unknown, mixed, positive, quantified, or guaranteed ROI wording deliberately fails closed.
    """
    roi_sentences = [sentence for sentence in _sentences(text) if _ROI_TERM_RE.search(sentence)]
    if not roi_sentences:
        return False
    for sentence in roi_sentences:
        if _ROI_OUTCOME_ASSERTION_RE.search(sentence):
            return False
        if not _ROI_EVALUATION_INTENT_RE.search(sentence):
            return False
    return True


def filter_roi_evaluation_intent_false_positive(failures: list[str], parsed: dict | None) -> list[str]:
    """Remove the ROI-outcome failure only for proven evaluation-intent-only manuscripts."""
    rows = list(failures or [])
    if ROI_OUTCOME_FAILURE not in rows:
        return rows
    parsed = parsed or {}
    article = str(parsed.get("note_draft") or "")
    action = str(parsed.get("action_text") or "")
    combined = "\n".join(part for part in (article, action) if part)
    if not roi_sentences_are_evaluation_intent_only(combined):
        return rows
    return [failure for failure in rows if failure != ROI_OUTCOME_FAILURE]


def install(pipeline_module: Any) -> Any:
    """Install conservative Fact false-positive filters; all unproven cases stay blocked."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_numeric = pipeline_module._find_unsupported_numeric_claims
    condition_compatible = pipeline_module._numeric_condition_compatible
    original_fact_gate = getattr(pipeline_module, "validate_fact_gate", None)

    def _find_unsupported_numeric_claims_with_equivalence(
        draft: str,
        source_context: str,
        evidence_metadata: dict | None = None,
    ) -> list[str]:
        failures = original_numeric(draft, source_context, evidence_metadata)
        return filter_numeric_false_positives(
            failures,
            draft,
            source_context,
            condition_compatible=condition_compatible,
        )

    pipeline_module._find_unsupported_numeric_claims = _find_unsupported_numeric_claims_with_equivalence

    if callable(original_fact_gate):
        def validate_fact_gate_with_precision(*args: Any, **kwargs: Any):
            ok, failures = original_fact_gate(*args, **kwargs)
            rows = list(failures or [])
            parsed = args[0] if args else kwargs.get("parsed", {})
            filtered = filter_roi_evaluation_intent_false_positive(rows, parsed)
            if len(filtered) != len(rows):
                logger = getattr(pipeline_module, "logger", None)
                if logger is not None:
                    logger.info("[RUN350 ROI INTENT PRECISION] removed evaluation-intent false positive")
            return (bool(ok) if filtered == rows else not filtered), list(dict.fromkeys(filtered))

        pipeline_module.validate_fact_gate = validate_fact_gate_with_precision
        pipeline_module.RUN350_ZERO_PROVIDER_CALLS = True

    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
