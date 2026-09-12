"""Shadow-only quality contract for Technology Intelligence product comments.

This module is deliberately network- and Notion-independent. It validates a challenger
candidate against a factual fixture and an immutable baseline, but it never authorizes a
production write. Existing non-empty product copy remains protected by
comment_write_contract.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping


SHADOW_FIELDS = ("main_risk", "best_for", "avoid_for", "short_rationale")
FIELD_LABELS = {
    "main_risk": "主リスク",
    "best_for": "向いている用途",
    "avoid_for": "向いていない用途",
    "short_rationale": "判断理由",
}
FIELD_LIMITS = {
    "main_risk": (18, 180),
    "best_for": (12, 160),
    "avoid_for": (12, 160),
    "short_rationale": (18, 220),
}

SHADOW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(SHADOW_FIELDS),
    "properties": {
        name: {"type": "string"} for name in SHADOW_FIELDS
    },
}


class TechnologyCommentShadowError(RuntimeError):
    pass


@dataclass(frozen=True)
class AxisScores:
    specificity: int
    decision_usefulness: int
    evidence_alignment: int
    naturalness: int
    concision: int

    @property
    def total(self) -> float:
        return round(
            (
                self.specificity
                + self.decision_usefulness
                + self.evidence_alignment
                + self.naturalness
                + self.concision
            ) / 5.0,
            1,
        )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "specificity": self.specificity,
            "decision_usefulness": self.decision_usefulness,
            "evidence_alignment": self.evidence_alignment,
            "naturalness": self.naturalness,
            "concision": self.concision,
            "total": self.total,
        }


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _validate_shape(values: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(values, Mapping) or set(values) != set(SHADOW_FIELDS):
        raise TechnologyCommentShadowError("shadow_shape_invalid")
    cleaned = {name: _clean(values[name]) for name in SHADOW_FIELDS}
    if any(not value for value in cleaned.values()):
        raise TechnologyCommentShadowError("shadow_empty_field")
    return cleaned


def build_shadow_prompt(fixture: Mapping[str, Any]) -> str:
    """Build a provider-neutral prompt whose sole factual surface is fixture evidence."""
    evidence = fixture.get("evidence")
    if not isinstance(evidence, list) or not evidence or any(not _clean(x) for x in evidence):
        raise TechnologyCommentShadowError("shadow_evidence_required")
    decision = fixture.get("decision_surface")
    if not isinstance(decision, Mapping):
        raise TechnologyCommentShadowError("shadow_decision_surface_required")

    return f"""あなたはAI Intelligence FactoryのTechnology Intelligence DB向けShadow Writerです。
これは品質比較専用です。本番DBへ書き込む権限はありません。既存値を書き換えてはいけません。

【目的】
既存の有料商品品質を超えられるか検証するため、次の4項目だけ候補文を作る。
- main_risk: 主リスク
- best_for: 向いている用途
- avoid_for: 向いていない用途
- short_rationale: 判断理由

【絶対ルール】
- 4項目の本文は必ず自然な日本語で書く。EVIDENCEが英語でも英訳のまま返してはいけない。
- 製品名・技術用語など必要な固有語以外、英語文を出力しない。
- 事実として使えるのは EVIDENCE だけ。
- DECISION SURFACE は判断材料であり、新しい事実ソースではない。
- EVIDENCEにない数値、機能、利用条件、因果、一般提供状況を創作しない。
- 評価条件を一般的な製品仕様や本番利用条件へ拡張しない。
- 各項目は短く具体的な1〜2文。一般論、テンプレ語、煽り、水増しを避ける。
- 「要検証」「注意が必要」だけで終わらず、何を・なぜ判断する文なのか具体化する。
- Markdown、箇条書き、HTML、AI/Provider自己言及は禁止。
- JSONオブジェクト1個だけを返す。4キー以外は禁止。

【EVIDENCE — sole factual surface】
{json.dumps(evidence, ensure_ascii=False)}

【DECISION SURFACE — judgment only】
{json.dumps(dict(decision), ensure_ascii=False)}
"""


def parse_shadow_output(raw_text: str) -> dict[str, str]:
    try:
        data = json.loads(str(raw_text or ""))
    except Exception:
        raise TechnologyCommentShadowError("shadow_json_invalid") from None
    return _validate_shape(data)


def _style_violations(field: str, text: str) -> list[str]:
    low, high = FIELD_LIMITS[field]
    violations: list[str] = []
    if not low <= len(text) <= high:
        violations.append("length_out_of_range")
    if not re.search(r"[ぁ-んァ-ヶ一-龯]", text):
        violations.append("japanese_required")
    if "\n" in text or "\r" in text:
        violations.append("multiline")
    if re.search(r"(^|\s)(#{1,6}|[-*+]\s|\d+[.)]\s)", text):
        violations.append("markdown_or_list")
    if "<br" in text.lower() or "</" in text.lower():
        violations.append("html")
    if re.search(r"\b(groq|gemini|openai|anthropic)\b|私はAI|AIとして", text, re.I):
        violations.append("provider_self_reference")
    sentences = [x for x in re.split(r"[。！？!?]+", text) if x.strip()]
    if len(sentences) > 2:
        violations.append("too_many_sentences")
    if re.search(r"重要です|有用です|注意が必要です|検討すべきです", text) and len(text) < 35:
        violations.append("generic_short_template")
    return violations


def _term_hits(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if _clean(term).lower() in lowered)


def score_values(values: Mapping[str, Any], fixture: Mapping[str, Any]) -> tuple[AxisScores, dict[str, list[str]]]:
    cleaned = _validate_shape(values)
    style = {field: _style_violations(field, text) for field, text in cleaned.items()}
    all_text = " ".join(cleaned.values())

    anchors = [_clean(x) for x in fixture.get("specificity_anchors", []) if _clean(x)]
    evidence_terms = [_clean(x) for x in fixture.get("evidence_terms", []) if _clean(x)]
    forbidden = [_clean(x) for x in fixture.get("forbidden_claims", []) if _clean(x)]
    action_terms = [_clean(x) for x in fixture.get("decision_terms", []) if _clean(x)]

    anchor_hits = _term_hits(all_text, anchors)
    specificity = min(100, 55 + anchor_hits * 15) if anchors else 70

    decision_hits = _term_hits(all_text, action_terms)
    decision_usefulness = min(100, 55 + decision_hits * 15) if action_terms else 70

    evidence_hits = _term_hits(all_text, evidence_terms)
    forbidden_hits = _term_hits(all_text, forbidden)
    evidence_alignment = min(100, 60 + evidence_hits * 10) - min(60, forbidden_hits * 30)
    evidence_alignment = max(0, evidence_alignment)

    violation_count = sum(len(rows) for rows in style.values())
    naturalness = max(0, 100 - violation_count * 25)

    target_lengths = {"main_risk": 90, "best_for": 70, "avoid_for": 70, "short_rationale": 120}
    distance = sum(abs(len(cleaned[k]) - target_lengths[k]) / target_lengths[k] for k in SHADOW_FIELDS) / 4
    concision = max(0, min(100, round(100 - distance * 45)))

    return AxisScores(
        specificity=int(specificity),
        decision_usefulness=int(decision_usefulness),
        evidence_alignment=int(evidence_alignment),
        naturalness=int(naturalness),
        concision=int(concision),
    ), style


def compare_shadow_to_baseline(
    baseline: Mapping[str, Any], challenger: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare immutable baseline and challenger. Ties always stay with baseline."""
    baseline_clean = _validate_shape(baseline)
    challenger_clean = _validate_shape(challenger)
    baseline_scores, baseline_style = score_values(baseline_clean, fixture)
    challenger_scores, challenger_style = score_values(challenger_clean, fixture)

    axis_names = ("specificity", "decision_usefulness", "evidence_alignment", "naturalness", "concision")
    strictly_better_axes = [
        name for name in axis_names
        if getattr(challenger_scores, name) > getattr(baseline_scores, name)
    ]
    worse_axes = [
        name for name in axis_names
        if getattr(challenger_scores, name) < getattr(baseline_scores, name)
    ]
    margin = round(challenger_scores.total - baseline_scores.total, 1)
    deterministic_gate = (
        margin >= 5.0
        and len(strictly_better_axes) >= 3
        and not worse_axes
        and not any(challenger_style.values())
        and challenger_scores.evidence_alignment >= 80
    )

    return {
        "baseline_scores": baseline_scores.as_dict(),
        "challenger_scores": challenger_scores.as_dict(),
        "margin": margin,
        "strictly_better_axes": strictly_better_axes,
        "worse_axes": worse_axes,
        "baseline_style_violations": baseline_style,
        "challenger_style_violations": challenger_style,
        "deterministic_gate_passed": deterministic_gate,
        "promotion_candidate": deterministic_gate,
        "automatic_promotion_allowed": False,
        "human_or_independent_semantic_review_required": True,
        "persist_allowed": False,
        "business_writes": 0,
        "tie_policy": "baseline_wins",
    }
