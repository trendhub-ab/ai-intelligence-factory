"""Run350: distinguish ROI evaluation intent from unsupported ROI outcome claims.

Real Run38 DeepSeek article was blocked by the Fact Gate because it ended with
"自社にとって投資対効果が見合うかを見極めていきましょう".  The source did not
measure ROI, but the article also did not claim an ROI outcome; it explicitly proposed
measuring/evaluating ROI during a bounded trial.

This overlay is deliberately narrow and provider-free.  It removes only the exact
``unsupported outcome extrapolation: ROI/financial outcome not measured by evidence``
failure when every ROI-bearing sentence is clearly evaluation intent rather than a
positive financial-result assertion.  Any mixed, numeric, directional, guaranteed,
or already-achieved ROI claim remains blocked by the original Fact Gate.
"""
from __future__ import annotations

import re
from typing import Any

ROI_OUTCOME_FAILURE = "unsupported outcome extrapolation: ROI/financial outcome not measured by evidence"
_INSTALLED_ATTR = "_run350_roi_evaluation_intent_precision_installed"

_ROI_TERM_RE = re.compile(r"\bROI\b|投資対効果|投資の成果|return on investment", re.I)

# Narrow action/evaluation verbs.  These describe a question to answer with local data,
# not a result already established by the source.
_EVALUATION_INTENT_RE = re.compile(
    r"(?:"
    r"(?:ROI|投資対効果|投資の成果).{0,36}(?:測|計測|測定|確認|検証|評価|比較|見極|判断|算出|試算|確かめ|チェック)|"
    r"(?:測|計測|測定|確認|検証|評価|比較|見極|判断|算出|試算|確かめ|チェック).{0,36}(?:ROI|投資対効果|投資の成果)|"
    r"投資対効果が見合うか|ROIが見合うか|return on investment.{0,36}(?:measure|evaluate|assess|check|estimate|calculate|validate)"
    r")",
    re.I,
)

# If one of these appears in the same ROI sentence, we fail closed.  They are outcome
# assertions (or quantified outcomes), not merely instructions to evaluate later.
_OUTCOME_ASSERTION_RE = re.compile(
    r"(?:"
    r"(?:ROI|投資対効果|投資の成果).{0,36}(?:高い|低い|良い|悪い|優れる|改善|向上|増加|上がる|下がる|確実|保証|十分|大きい|小さい|見合う(?:。|です|といえる|と言える))|"
    r"(?:高い|低い|良い|悪い|優れる|改善|向上|増加|確実|保証).{0,36}(?:ROI|投資対効果|投資の成果)|"
    r"(?:ROI|投資対効果|投資の成果).{0,24}(?:\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*[倍x×]|黒字|赤字|回収|利益|収益)|"
    r"return on investment.{0,36}(?:high|low|better|improv|increase|decrease|guarantee|positive|negative|profitable)"
    r")",
    re.I,
)


def _sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"(?<=[。！？!?])|\n+", str(text or ""))
        if part and part.strip()
    ]


def roi_sentences_are_evaluation_intent_only(text: str) -> bool:
    """Return True only when every ROI-bearing sentence is a bounded evaluation intent.

    Fail closed on mixed intent/outcome wording, quantified ROI, or any ROI sentence whose
    semantics are not covered by the narrow allowlist above.
    """
    roi_sentences = [sentence for sentence in _sentences(text) if _ROI_TERM_RE.search(sentence)]
    if not roi_sentences:
        return False
    for sentence in roi_sentences:
        if _OUTCOME_ASSERTION_RE.search(sentence):
            return False
        if not _EVALUATION_INTENT_RE.search(sentence):
            return False
    return True


def install(pipeline_module: Any) -> Any:
    """Wrap the final Fact Gate and remove only the proven ROI-intent false positive."""
    p = pipeline_module
    if bool(getattr(p, _INSTALLED_ATTR, False)):
        return p
    original = getattr(p, "validate_fact_gate", None)
    if not callable(original):
        return p

    def validate_fact_gate_with_roi_intent_precision(*args: Any, **kwargs: Any):
        ok, failures = original(*args, **kwargs)
        failures = list(failures or [])
        if ROI_OUTCOME_FAILURE not in failures:
            return bool(ok), failures

        parsed = args[0] if args else kwargs.get("parsed", {})
        parsed = parsed or {}
        article = str(parsed.get("note_draft") or "")
        action = str(parsed.get("action_text") or "")
        combined = "\n".join(part for part in (article, action) if part)
        if roi_sentences_are_evaluation_intent_only(combined):
            failures = [failure for failure in failures if failure != ROI_OUTCOME_FAILURE]
            logger = getattr(p, "logger", None)
            if logger is not None:
                logger.info("[RUN350 ROI INTENT PRECISION] removed evaluation-intent false positive")
        return (not failures), list(dict.fromkeys(failures))

    p.validate_fact_gate = validate_fact_gate_with_roi_intent_precision
    setattr(p, _INSTALLED_ATTR, True)
    p.RUN350_ZERO_PROVIDER_CALLS = True
    return p
