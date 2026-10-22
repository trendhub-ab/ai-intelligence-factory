"""Provider-free diagnostic for V3's question/insight lost between planning and prose.

This is an editorial review aid, NOT a quality score, Gate, proof of semantic
entailment, or permission to publish. Shared Phase 0 A/B baselines are immutable.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any, Mapping

_FIELDS = {
    "question": ("Writer Reaction", "Question"),
    "evidence_pivot": ("Editorial Discovery", "Evidence Pivot"),
    "after_view": ("Cognitive Shift", "After View"),
    "discovery": ("Cognitive Shift", "What I Now Find Interesting"),
}
_AUDIT_VERSION = 1


def _field(text: str, field: str) -> str:
    pattern = rf"(?im)^\s*(?:[-*]\s*)?{re.escape(field)}\s*[:：]\s*(.*?)\s*$"
    match = re.search(pattern, str(text or ""))
    return match.group(1).strip() if match else ""


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(c.lower() for c in text if c.isalnum() or c in "ぁ-んァ-ン一-龥")


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
    retention = {key: _surface_retained(anchor, final) for key, anchor in anchors.items()}
    # Detect a *measurable* review-stage removal without punishing minimal edits.
    draft_has_writer = "私" in draft
    final_has_writer = "私" in final
    question_marks = ("?", "？")
    final_has_question = any(symbol in final for symbol in question_marks)
    headings = re.findall(r"(?m)^#{2,4}\s*(.+?)\s*$", final)
    fixed_v1_intro = len(headings) >= 3 and headings[:3] == [
        "どんな内容？", "なぜ重要？", "結論は？"
    ]
    flags = []
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
    return {
        "audit_version": _AUDIT_VERSION,
        "scope": "editorial_surface_diagnostic_only",
        "not_a_quality_score": True,
        "not_publication_authority": True,
        "writer_voice_visible": final_has_writer,
        "question_punctuation_visible": final_has_question,
        "planning_anchor_status": retention,
        "review_stage_changed_prose": draft.strip() != final.strip(),
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
