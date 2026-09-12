"""Shadow-only rich comment candidate contract for future Groq evaluation.

This module builds and validates a structured prompt/response contract but NEVER calls a
provider and NEVER writes Notion. Production comment ownership remains frozen. The goal is
to make future Groq candidates comparable against completed Content DB golden samples
without weakening Fact Boundary or permitting automatic promotion.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from groq_article_parity import load_input
from hybrid_fact_boundary import audit_fact_boundary
from hybrid_fact_envelope import build_fact_envelope, validate_fact_envelope
from hybrid_groq_plan import load_hybrid_plan_report
from hybrid_notion_comment_contract import PRESERVE_EXISTING, SHADOW_ONLY


class CommentShadowError(RuntimeError):
    pass


COMMENT_SHADOW_FIELDS = (
    "what",
    "why_important",
    "decision_reason",
    "next_action",
)

COMMENT_SHADOW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(COMMENT_SHADOW_FIELDS),
    "properties": {
        "what": {"type": "string", "minLength": 20, "maxLength": 220},
        "why_important": {"type": "string", "minLength": 20, "maxLength": 260},
        "decision_reason": {"type": "string", "minLength": 20, "maxLength": 360},
        "next_action": {"type": "string", "minLength": 12, "maxLength": 300},
    },
}

FIELD_TO_NOTION = {
    "what": "これは何？",
    "why_important": "なぜ重要？",
    "decision_reason": "判断理由",
    "next_action": "次にやること",
}


def _load_bound_inputs(input_path: str, plan_report_path: str) -> tuple[dict, dict, dict]:
    item = load_input(input_path)
    envelope = validate_fact_envelope(build_fact_envelope(input_path))
    report = json.loads(Path(plan_report_path).read_text(encoding="utf-8"))
    if report.get("mode") != "hybrid_groq_judgment_fact_locked":
        raise CommentShadowError("comment_shadow_fact_locked_plan_required")
    if report.get("status") != "PLAN_VALIDATED" or report.get("semantic_plan_validated") is not True:
        raise CommentShadowError("comment_shadow_plan_not_validated")
    if report.get("candidate_id") != item.get("candidate_id"):
        raise CommentShadowError("comment_shadow_candidate_mismatch")
    if report.get("fact_envelope_sha256") != envelope.get("fact_ledger_sha256"):
        raise CommentShadowError("comment_shadow_fact_hash_mismatch")
    plan = load_hybrid_plan_report(plan_report_path)
    return item, envelope, plan


def build_comment_shadow_fixture(input_path: str, plan_report_path: str, output_path: str | None = None) -> dict:
    item, envelope, plan = _load_bound_inputs(input_path, plan_report_path)
    decision_surface = {
        "decision": plan["decision"],
        "decision_reason": plan["decision_reason"],
        "business_impact": plan["business_impact"],
        "technical_impact": plan["technical_impact"],
        "urgency": plan["urgency"],
        "market_impact": plan["market_impact"],
        "reliability": plan["reliability"],
        "article_value": plan["article_value"],
        "access_status": plan["access_status"],
        "action": plan["action"],
    }
    prompt = f"""あなたはAI Intelligence FactoryのNotionコメント品質比較用Shadow Writerです。
本番DBへは一切書き込みません。既存コメントを書き換える権限もありません。

【目的】
既存Content Intelligence DBの完成済みコメントと品質比較するため、4項目だけ候補文を作る。

【事実ルール】
- 事実の上限はSOURCE CONTEXTだけ。
- DECISION SURFACEは判断・方向性であり、新しい事実ソースではない。
- SOURCE CONTEXTにない数値、機能、利用条件、因果、固有名詞を追加しない。
- 推測を事実として書かない。
- access_status=NOT_CONFIRMEDなら一般利用可能と断定しない。
- 評価条件を本番・一般利用条件へ拡張しない。

【既存品質から抽出した表現契約】
- 抽象語だけで終わらせず、SOURCE CONTEXTにある具体的な対象・変更・条件を使う。
- what: 1文中心。何が出た/変わったかを具体的に説明する。
- why_important: 1〜2文。実務への便益と制約・注意点を必要に応じて同居させる。
- decision_reason: 1〜3個の具体的根拠を自然な文章でまとめる。単なる「重要だから」「監視価値がある」で終わらせない。
- next_action: 読者が次に実行できる確認・PoC・比較を具体化する。ただしSOURCE CONTEXTにない製品名、コマンド、設定値、手順を創作しない。
- Markdown見出し、箇条書き、HTML、プロバイダー自己言及は禁止。
- 煽り、断定強化、一般論の水増しは禁止。

【SOURCE CONTEXT — sole factual surface】
{envelope['fact_ledger']}

【DECISION SURFACE — judgment only】
{json.dumps(decision_surface, ensure_ascii=False)}

JSONオブジェクト1個だけを返す。必須キーは {', '.join(COMMENT_SHADOW_FIELDS)} の4個のみ。
"""
    fixture = {
        "mode": SHADOW_ONLY,
        "candidate_id": item["candidate_id"],
        "provider_target": "groq",
        "model_target": "openai/gpt-oss-120b",
        "schema": COMMENT_SHADOW_SCHEMA,
        "prompt": prompt,
        "fact_envelope_sha256": envelope["fact_ledger_sha256"],
        "existing_value_policy": PRESERVE_EXISTING,
        "persist_allowed": False,
        "business_writes": 0,
        "automatic_promotion_allowed": False,
    }
    if output_path:
        Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def _style_violations(field: str, value: str) -> list[str]:
    text = str(value or "").strip()
    limits = {"what": 220, "why_important": 260, "decision_reason": 360, "next_action": 300}
    violations: list[str] = []
    if not text:
        violations.append("empty")
    if len(text) > limits[field]:
        violations.append("too_long")
    if "\n" in text or "\r" in text:
        violations.append("multiline")
    if re.search(r"(^|\s)(#{1,6}|[-*+]\s|\d+[.)]\s)", text):
        violations.append("markdown_or_list")
    if "<br" in text.lower() or "</" in text.lower():
        violations.append("html")
    if any(token in text.lower() for token in ("私はai", "as an ai", "geminiとして", "groqとして")):
        violations.append("provider_self_reference")
    sentence_count = len([x for x in re.split(r"[。！？!?]+", text) if x.strip()])
    max_sentences = 1 if field == "what" else (3 if field == "decision_reason" else 2)
    if sentence_count > max_sentences:
        violations.append("too_many_sentences")
    return violations


def validate_comment_shadow_output(input_path: str, plan_report_path: str, raw_text: str) -> dict:
    item, envelope, _ = _load_bound_inputs(input_path, plan_report_path)
    try:
        data = json.loads(str(raw_text or ""))
    except Exception:
        raise CommentShadowError("comment_shadow_json_invalid") from None
    if not isinstance(data, dict) or set(data) != set(COMMENT_SHADOW_FIELDS):
        raise CommentShadowError("comment_shadow_shape_invalid")
    from jsonschema import Draft202012Validator
    try:
        Draft202012Validator(COMMENT_SHADOW_SCHEMA).validate(data)
    except Exception:
        raise CommentShadowError("comment_shadow_schema_invalid") from None

    style = {field: _style_violations(field, data[field]) for field in COMMENT_SHADOW_FIELDS}
    notion_values = {FIELD_TO_NOTION[field]: str(data[field]).strip() for field in COMMENT_SHADOW_FIELDS}
    combined = "\n".join(notion_values.values())
    fact = audit_fact_boundary(envelope["fact_ledger"], combined)
    passed = fact["passed"] and all(not rows for rows in style.values())
    return {
        "mode": SHADOW_ONLY,
        "candidate_id": item["candidate_id"],
        "values": notion_values,
        "style_violations": style,
        "fact_boundary": fact,
        "passed": passed,
        "persist_allowed": False,
        "business_writes": 0,
        "automatic_promotion_allowed": False,
        "human_semantic_review_required": True,
    }
