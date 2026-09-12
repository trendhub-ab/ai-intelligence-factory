"""Provider-free ownership and shadow-migration contract for Notion comment properties.

This module deliberately performs no Notion writes and no model calls. Existing values are
preserved. It classifies comment-like properties by current authority and exposes only a
small Fact-Locked shadow surface for parity comparison before any provider migration.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from hybrid_fact_boundary import audit_fact_boundary
from hybrid_groq_plan import load_hybrid_plan_report


class CommentContractError(RuntimeError):
    pass


PRESERVE_EXISTING = "PRESERVE_EXISTING"
SHADOW_ONLY = "SHADOW_ONLY"
PRODUCTION_FROZEN = "PRODUCTION_FROZEN"

SOURCE_INHERITED = "source_inherited"
SCREENING_EXISTING = "screening_existing"
FACT_LOCKED_PLAN_DETERMINISTIC = "fact_locked_plan_deterministic"
LEGACY_ARTICLE_MANAGEMENT_FROZEN = "legacy_article_management_frozen"
LEGACY_PRODUCT_REVIEW_FROZEN = "legacy_product_review_frozen"
SYSTEM_DETERMINISTIC = "system_deterministic"
EXTERNAL_REVIEW_OR_FORMULA = "external_review_or_formula"

CONTENT_COMMENT_CONTRACT = {
    "スコア内訳": (FACT_LOCKED_PLAN_DETERMINISTIC, SHADOW_ONLY),
    "これは何？": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "なぜ重要？": (FACT_LOCKED_PLAN_DETERMINISTIC, SHADOW_ONLY),
    "なぜ重要ではない？": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "対象": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "次にやること": (FACT_LOCKED_PLAN_DETERMINISTIC, SHADOW_ONLY),
    "パラダイム変化": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "代替比較": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "移行コスト": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "元情報要約": (SOURCE_INHERITED, PRODUCTION_FROZEN),
    "判断理由": (FACT_LOCKED_PLAN_DETERMINISTIC, SHADOW_ONLY),
    "向いている人": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "向いていない人": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "今後の見通し": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
    "選別理由": (SCREENING_EXISTING, PRODUCTION_FROZEN),
    "公開要約": (LEGACY_ARTICLE_MANAGEMENT_FROZEN, PRODUCTION_FROZEN),
}

# Production notion_payloads.py config keys that feed comment-like Content DB fields.
# CI statically binds these surfaces to the ownership inventory so a new payload field
# cannot silently bypass migration governance.
CONTENT_PAYLOAD_CONFIG_MAP = {
    "PROP_SCORE_BREAKDOWN": "スコア内訳",
    "PROP_WHAT": "これは何？",
    "PROP_WHY_IMPORTANT": "なぜ重要？",
    "PROP_WHY_NOT_IMPORTANT": "なぜ重要ではない？",
    "PROP_WHO": "対象",
    "PROP_ACTION": "次にやること",
    "PROP_PARADIGM_SHIFT": "パラダイム変化",
    "PROP_ALTERNATIVE_COMPARISON": "代替比較",
    "PROP_MIGRATION_COST": "移行コスト",
    "PROP_SOURCE_SUMMARY": "元情報要約",
    "PROP_DECISION_REASON": "判断理由",
    "PROP_WHO_SHOULD_USE": "向いている人",
    "PROP_WHO_SHOULD_NOT_USE": "向いていない人",
    "PROP_FUTURE_SCENARIO": "今後の見通し",
    "PROP_SCREENING_REASON": "選別理由",
}

TECHNOLOGY_COMMENT_CONTRACT = {
    "主リスク（内部）": (LEGACY_PRODUCT_REVIEW_FROZEN, SHADOW_ONLY),
    "向いている用途（内部）": (LEGACY_PRODUCT_REVIEW_FROZEN, SHADOW_ONLY),
    "向いていない用途（内部）": (LEGACY_PRODUCT_REVIEW_FROZEN, SHADOW_ONLY),
    "判断理由（内部）": (LEGACY_PRODUCT_REVIEW_FROZEN, SHADOW_ONLY),
    "わかりやすい要約（内部）": (EXTERNAL_REVIEW_OR_FORMULA, PRODUCTION_FROZEN),
    "今回の話題（内部）": (EXTERNAL_REVIEW_OR_FORMULA, PRODUCTION_FROZEN),
    "追跡理由": (SYSTEM_DETERMINISTIC, PRODUCTION_FROZEN),
    "選別理由": (SYSTEM_DETERMINISTIC, PRODUCTION_FROZEN),
    "元情報要約": (SYSTEM_DETERMINISTIC, PRODUCTION_FROZEN),
    "推奨アクション理由": (SYSTEM_DETERMINISTIC, PRODUCTION_FROZEN),
    "一次情報URL（内部）": (SOURCE_INHERITED, PRODUCTION_FROZEN),
}

TECHNOLOGY_CORE_CONSTANT_MAP = {
    "TECH_PROP_MAIN_RISK": "主リスク（内部）",
    "TECH_PROP_BEST_FOR": "向いている用途（内部）",
    "TECH_PROP_AVOID_FOR": "向いていない用途（内部）",
    "TECH_PROP_SHORT_RATIONALE": "判断理由（内部）",
    "TECH_PROP_TRACKING_REASON": "追跡理由",
    "TECH_PROP_SCREENING_REASON": "選別理由",
    "TECH_PROP_SOURCE_SUMMARY": "元情報要約",
    "TECH_PROP_EVIDENCE_URLS": "一次情報URL（内部）",
}

PRODUCT_REVIEW_DIRECT_FIELDS = {
    "main_risk": ("主リスク（内部）", 220),
    "best_for": ("向いている用途（内部）", 220),
    "avoid_for": ("向いていない用途（内部）", 220),
    "short_rationale": ("判断理由（内部）", 260),
}


def property_contract(database: str, property_name: str) -> dict:
    contracts = {"content": CONTENT_COMMENT_CONTRACT, "technology": TECHNOLOGY_COMMENT_CONTRACT}
    if database not in contracts:
        raise CommentContractError("comment_database_unknown")
    row = contracts[database].get(property_name)
    if row is None:
        raise CommentContractError("comment_property_unknown")
    authority, migration = row
    return {
        "database": database,
        "property": property_name,
        "authority": authority,
        "migration": migration,
        "existing_value_policy": PRESERVE_EXISTING,
        "direct_groq_freeform_allowed": False,
        "direct_writer_article_source_allowed": False,
    }


def _strict_fact_locked_plan(plan_report_path: str) -> dict:
    try:
        report = json.loads(Path(plan_report_path).read_text(encoding="utf-8"))
    except Exception:
        raise CommentContractError("comment_shadow_plan_report_invalid") from None
    if not isinstance(report, dict):
        raise CommentContractError("comment_shadow_plan_report_invalid")
    if report.get("mode") != "hybrid_groq_judgment_fact_locked":
        raise CommentContractError("comment_shadow_fact_locked_plan_required")
    if report.get("status") != "PLAN_VALIDATED" or report.get("semantic_plan_validated") is not True:
        raise CommentContractError("comment_shadow_validated_plan_required")
    if not isinstance(report.get("fact_envelope_sha256"), str) or len(report["fact_envelope_sha256"]) != 64:
        raise CommentContractError("comment_shadow_fact_hash_required")
    if not isinstance(report.get("composed_plan"), dict):
        raise CommentContractError("comment_shadow_composed_plan_required")
    return load_hybrid_plan_report(plan_report_path)


def _score_breakdown(plan: Mapping) -> str:
    return (
        f"Business Impact {plan['business_impact']}/25 / "
        f"Technical Impact {plan['technical_impact']}/25 / "
        f"Urgency {plan['urgency']}/20 / "
        f"Market Impact {plan['market_impact']}/15 / "
        f"Reliability {plan['reliability']}/15"
    )


def build_content_comment_shadow(plan_report_path: str) -> dict:
    plan = _strict_fact_locked_plan(plan_report_path)
    values = {
        "スコア内訳": _score_breakdown(plan),
        "なぜ重要？": str(plan["why_important"]),
        "判断理由": " ".join(str(x) for x in plan["decision_reason"]),
        "次にやること": str(plan["action"]),
    }
    if set(values) != {name for name, (_, state) in CONTENT_COMMENT_CONTRACT.items() if state == SHADOW_ONLY}:
        raise CommentContractError("content_shadow_contract_drift")
    return {
        "mode": SHADOW_ONLY, "persist_allowed": False,
        "existing_value_policy": PRESERVE_EXISTING,
        "source": FACT_LOCKED_PLAN_DETERMINISTIC, "values": values,
    }


def validate_product_review_comment_style(field: str, text: str) -> dict:
    spec = PRODUCT_REVIEW_DIRECT_FIELDS.get(field)
    if spec is None:
        raise CommentContractError("product_review_comment_field_unknown")
    _, limit = spec
    value = str(text or "").strip()
    violations: list[str] = []
    if not value:
        violations.append("empty")
    if len(value) > limit:
        violations.append("too_long")
    if "\n" in value or "\r" in value:
        violations.append("multiline")
    if re.search(r"(^|\s)(#{1,6}|[-*+]\s|\d+[.)]\s)", value):
        violations.append("markdown_or_list")
    if any(token in value.lower() for token in ("私はai", "as an ai", "geminiとして", "groqとして")):
        violations.append("provider_self_reference")
    sentence_count = len([x for x in re.split(r"[。！？!?]+", value) if x.strip()])
    if sentence_count > 2:
        violations.append("too_many_sentences")
    return {
        "field": field, "passed": not violations, "violations": violations,
        "chars": len(value), "sentences": sentence_count, "persist_allowed": False,
    }


def audit_product_review_shadow_fact_boundary(source_context: str, assessment: Mapping) -> dict:
    chunks = []
    style = {}
    for field in PRODUCT_REVIEW_DIRECT_FIELDS:
        value = str(assessment.get(field) or "")
        style[field] = validate_product_review_comment_style(field, value)
        chunks.append(value)
    fact = audit_fact_boundary(source_context, "\n".join(chunks))
    return {
        "mode": SHADOW_ONLY, "persist_allowed": False, "style": style,
        "fact_boundary": fact,
        "passed": fact["passed"] and all(row["passed"] for row in style.values()),
    }


def compare_comment_style(existing: str, candidate: str) -> dict:
    old = str(existing or "").strip()
    new = str(candidate or "").strip()
    old_sentences = len([x for x in re.split(r"[。！？!?]+", old) if x.strip()])
    new_sentences = len([x for x in re.split(r"[。！？!?]+", new) if x.strip()])
    ratio = len(new) / len(old) if old else None
    return {
        "existing_chars": len(old), "candidate_chars": len(new), "length_ratio": ratio,
        "sentence_count_delta": new_sentences - old_sentences,
        "candidate_multiline": "\n" in new or "\r" in new,
        "candidate_has_markdown": bool(re.search(r"(^|\s)(#{1,6}|[-*+]\s|\d+[.)]\s)", new)),
        "semantic_equivalence_claimed": False, "persist_allowed": False,
    }


def evaluate_shadow_promotion(existing_values: Mapping, candidate_values: Mapping, *, machine_checks_passed: bool) -> dict:
    """Return evidence for review, never an automatic production migration approval."""
    comparisons = {}
    for name, candidate in candidate_values.items():
        if name not in existing_values:
            raise CommentContractError("shadow_existing_value_missing")
        comparisons[name] = compare_comment_style(str(existing_values[name]), str(candidate))
    return {
        "machine_checks_passed": bool(machine_checks_passed),
        "comparisons": comparisons,
        "human_semantic_review_required": True,
        "automatic_promotion_allowed": False,
        "production_write_allowed": False,
        "existing_value_policy": PRESERVE_EXISTING,
        "reason": "comment_migration_requires_explicit_quality_parity_review",
    }
