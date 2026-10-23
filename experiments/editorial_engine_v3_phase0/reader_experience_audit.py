"""Provider-free diagnostic for V3's question/insight lost between planning and prose.

This is an editorial review aid, NOT a quality score, Gate, proof of semantic
entailment, or permission to publish. Shared Phase 0 A/B baselines are immutable.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

_FIELDS = {
    "question": ("Writer Reaction", "Question"),
    "evidence_pivot": ("Editorial Discovery", "Evidence Pivot"),
    "after_view": ("Cognitive Shift", "After View"),
    "discovery": ("Cognitive Shift", "What I Now Find Interesting"),
}
# Human-review prompts only; these expressions are not automatic quality gates.
# Record exact phrases rather than counting first-person pronouns, questions, or
# legitimate discussion of technical limits as stylistic defects.
_FORMULAIC_WRITER_PHRASES = (
    "私が特に注目したのは",
    "ここで私の中で",
    "ここで私は見方を",
    "以前の私は",
    "以前は私は",
    "私は大きな期待を",
    "非常に実用的",
    "非常に重要な教訓",
    "いま私が最も面白いと感じているのは",
)


# Literal signs of business-report wording in real P4 drafts. Merely a human
# review aid: a technical article can have a justified formal passage.
_OVERFORMAL_REPORT_PHRASES = (
    "非常に重要な教訓",
    "ことが求められます",
    "重要な示唆を与え",
    "価値は十分にあります",
    "検証を進めてみるのがよさそうです",
    "継続して利用することが現実的です",
)


# Potential rather than proven provenance issues. Lexical cues cannot prove
# whether an autobiographical memory or industry forecast is false.
_POSSIBLE_PAST_BELIEF = re.compile(
    r"(?:以前は|以前の私は|かつて|もともと)(?:[^。！？\n]{0,36})(?:思っていた|信じていた|考えていた)"
)
_POSSIBLE_PROMISES = (
    "これからのスタンダードになる",
    "業界標準になる",
    "試さない手はありません",
    "必ず変わる",
    "予感がしています",
)


_AUDIT_VERSION = 1


def _field(text: str, field: str) -> str:
    pattern = rf"(?im)^\s*(?:[-*]\s*)?{re.escape(field)}\s*[:：]\s*(.*?)\s*$"
    match = re.search(pattern, str(text or ""))
    return match.group(1).strip() if match else ""


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(c.lower() for c in text if c.isalnum())


def _surface_retained(anchor: str, article: str) -> str:
    """Conservative *surface* proxy; lexical loss is never semantic proof."""
    source = _normalized(anchor)
    target = _normalized(article)
    if len(source) < 8 or len(target) < 12:
        return "not_evaluable"
    if source in target:
        return "surface_present"
    # Japanese character windows tolerate edited sentence endings and order.
    windows = {source[i:i + 3] for i in range(len(source) - 2)}
    # Short generic chunks can overlap unrelated writing; require a strong ratio.
    overlap = sum(1 for item in windows if item in target)
    ratio = overlap / len(windows) if windows else 0.0
    if ratio >= 0.55:
        return "surface_present"
    # A missing string cannot establish that the idea disappeared.
    return "review_for_possible_loss"


def diagnose_case(stages: Mapping[str, str]) -> dict[str, Any]:
    draft = str(stages.get("Persona Article Generation") or "")
    final = str(stages.get("Fact-Safe Review") or "")
    anchors = {
        key: _field(stages.get(stage, ""), label)
        for key, (stage, label) in _FIELDS.items()
    }
    draft_retention = {key: _surface_retained(anchor, draft) for key, anchor in anchors.items()}
    retention = {key: _surface_retained(anchor, final) for key, anchor in anchors.items()}
    stage_attribution = {}
    for key in anchors:
        before, after = draft_retention[key], retention[key]
        if before == "not_evaluable" or after == "not_evaluable":
            stage_attribution[key] = "not_evaluable"
        elif before == "review_for_possible_loss":
            stage_attribution[key] = (
                "possible_loss_during_article_generation"
                if after == "review_for_possible_loss" else "surface_reintroduced_in_review"
            )
        elif after == "review_for_possible_loss":
            stage_attribution[key] = "possible_loss_during_fact_safe_review"
        else:
            stage_attribution[key] = "surface_preserved"
    # Detect a *measurable* review-stage removal without punishing minimal edits.
    draft_has_writer = "私" in draft
    final_has_writer = "私" in final
    question_marks = ("?", "？")
    final_has_question = any(symbol in final for symbol in question_marks)
    headings = re.findall(r"(?m)^#{2,4}\s*(.+?)\s*$", final)
    fixed_v1_intro = len(headings) >= 3 and headings[:3] == [
        "どんな内容？", "なぜ重要？", "結論は？"
    ]
    formulaic = [
        phrase for phrase in _FORMULAIC_WRITER_PHRASES if phrase in final
    ]
    overformal = [
        phrase for phrase in _OVERFORMAL_REPORT_PHRASES if phrase in final
    ]
    possible_history = [m.group(0) for m in _POSSIBLE_PAST_BELIEF.finditer(final)]
    possible_promises = [phrase for phrase in _POSSIBLE_PROMISES if phrase in final]
    flags = []
    if possible_history:
        flags.append("possible_fabricated_writer_history")
    if possible_promises:
        flags.append("possible_unsupported_promise")
    if formulaic:
        flags.append("formulaic_writer_narration")
    if overformal:
        flags.append("overformal_report_tone")
    if draft_has_writer and not final_has_writer:
        flags.append("first_person_removed_in_fact_review")
    if not final_has_writer:
        flags.append("writer_voice_not_visible")
    if not final_has_question:
        flags.append("writer_question_not_visible")
    if fixed_v1_intro:
        flags.append("fixed_v1_summary_intro")
    for key, status in retention.items():
        if status == "review_for_possible_loss":
            flags.append(f"{key}_surface_not_retained")
        if stage_attribution[key] == "possible_loss_during_article_generation":
            flags.append(f"{key}_possible_loss_in_article_generation")
        elif stage_attribution[key] == "possible_loss_during_fact_safe_review":
            flags.append(f"{key}_possible_loss_in_fact_safe_review")
    return {
        "audit_version": _AUDIT_VERSION,
        "scope": "editorial_surface_diagnostic_only",
        "not_a_quality_score": True,
        "not_publication_authority": True,
        "writer_voice_visible": final_has_writer,
        "question_punctuation_visible": final_has_question,
        "planning_anchor_status": retention,
        "planning_anchor_in_article_generation": draft_retention,
        "possible_loss_stage": stage_attribution,
        "review_stage_changed_prose": draft.strip() != final.strip(),
        "formulaic_writer_phrases": formulaic,
        "overformal_report_phrases": overformal,
        "possible_writer_history_phrases": possible_history,
        "possible_promise_phrases": possible_promises,
        "review_flags": flags,
        "human_review_required": True,
    }


def audit_state(state: Mapping[str, Any]) -> dict[str, Any]:
    cases = list(state.get("cases") or [])
    mode = str(state.get("mode") or "FULL")
    if mode == "C_ONLY_REFINEMENT":
        completed = set(state.get("c_completed_case_ids") or [])
        cases = [case for case in cases if case.get("case_id") in completed]
    results = []
    for case in cases:
        stages = dict(case.get("editorial_stage_outputs") or {})
        outputs = dict(case.get("outputs") or {})
        if not outputs.get("C_EDITORIAL_ENGINE") or not stages.get("Fact-Safe Review"):
            continue
        if str(outputs["C_EDITORIAL_ENGINE"]).strip() != str(stages["Fact-Safe Review"]).strip():
            # Do not diagnose an untrusted/mismatched checkpoint as a valid C result.
            continue
        results.append({"case_id":str(case.get("case_id") or ""),
                        "diagnostic":diagnose_case(stages)})
    return {
        "audit_version":_AUDIT_VERSION,
        "scope":"diagnostics only; does not evaluate subjective interestingness",
        "cases":results,
        "human_blind_acceptance_still_required":True,
        "provider_calls":0,
    }
