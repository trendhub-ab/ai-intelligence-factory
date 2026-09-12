"""Hybrid-only Groq judgment adapter with deterministic Fact Envelope.

Verified evidence is locked before Groq. Groq may judge, score and propose editorial framing,
but it no longer writes source_summary/what. The final Decision Plan is composed locally from
the immutable envelope plus the validated Groq judgment.
"""
from __future__ import annotations

import json
from pathlib import Path

from groq_article_parity import load_input
from groq_rate_policy import GPT_OSS_120B, policy_for_model
from groq_two_pass_article import PLAN_SCHEMA, validate_plan, TwoPassArticleError
from hybrid_fact_envelope import build_fact_envelope, validate_fact_envelope

MODE = "json_object_local_strict"

JUDGMENT_FIELDS = [
    "why_important", "decision", "decision_reason", "business_impact", "technical_impact",
    "urgency", "market_impact", "reliability", "action", "article_value", "article_angle",
    "reader_bridge", "title_seed", "access_status",
]
JUDGMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": JUDGMENT_FIELDS,
    "properties": {key: PLAN_SCHEMA["properties"][key] for key in JUDGMENT_FIELDS},
}


def build_hybrid_plan_fixture(input_path: str, output_path: str) -> dict:
    item = load_input(input_path)
    envelope = validate_fact_envelope(build_fact_envelope(input_path))
    policy = policy_for_model(GPT_OSS_120B.model)
    exact_keys = ", ".join(JUDGMENT_FIELDS)
    prompt = f"""あなたはAI Intelligence FactoryのDecision Judgeです。
事実を書き直す担当ではありません。FACT ENVELOPEはプログラムで固定された読み取り専用Evidenceです。
あなたの担当は、確認済みEvidenceを解釈し、判断・採点・実務アクション・編集方針だけを返すことです。

【絶対ルール】
- source_summary / what は出力しない。事実の要約・言い換え・再構成をしない。
- FACT ENVELOPEにない事実、数値、日付、固有名詞、条件、時制、提供範囲、安全策の状態を追加しない。
- 評価条件を提供条件へ、安全策の公開時方針を評価時の適用事実へ変換しない。
- 安全策の名称から有効性・無効性・検証実施の有無を推測しない。必要なら「この資料から有効性は確認できない」と判断理由に書く。
- アクセス可否が確認できない場合 access_status=NOT_CONFIRMED。Actionは条件確認までとし、PoC、申請、導入、試用を勧めない。
- reliabilityはEvidence自体の信頼性。アクセス未確認をreliabilityへ重複減点しない。
- business_impact / technical_impact / urgency / market_impact は各軸を独立採点し、同じ不確実性を全軸へ重複減点しない。
- article_valueは導入可否とは別に、確認済み発見が読者へ与える理解・判断材料を評価する。
- article_angle / reader_bridge / title_seed は編集案であり、新しいFactを含めない。自然な日本語で書く。
- 読者は中学生〜非エンジニアも含む。reader_bridgeは具体的な理解の橋渡しにする。
- JSONオブジェクト1個だけを返す。Markdown、コードフェンス、前置き、後書きは禁止。
- 必須キーは次の14個だけ。すべて1回ずつ含め、余分なキーは禁止: {exact_keys}
- decision は NOW / TRY / WATCH / WAIT / AVOID のいずれか。
- access_status は CONFIRMED_AVAILABLE / NOT_CONFIRMED / NOT_RELEVANT のいずれか。
- business_impact=0..25、technical_impact=0..25、urgency=0..20、market_impact=0..15、reliability=0..15、article_value=0..100 の整数。
- decision_reason は1〜3個の文字列配列。それ以外の説明項目は文字列。

【候補】
Name: {item['name']}
Screening Score: {item['screening_score']}
Screening Reason: {item['screening_reason']}

【FACT ENVELOPE — READ ONLY】
{json.dumps(envelope, ensure_ascii=False)}
"""
    fixture = {
        "stage": "article",
        "provider": "groq",
        "model": GPT_OSS_120B.model,
        "rate_policy": policy.name,
        "prompt": prompt,
        "max_output_tokens": 2200,
        "reasoning_effort": "medium",
        "schema": JUDGMENT_SCHEMA,
        "candidate_id": item["candidate_id"],
        "pass": "decision_judgment",
        "structured_output_mode": MODE,
        "fact_envelope": envelope,
        "persist_results": False,
        "business_writes": 0,
    }
    Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def _parse_judgment_text(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("hybrid_judgment_empty")
    try:
        data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise ValueError("hybrid_judgment_json_invalid") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(JUDGMENT_SCHEMA).validate(data)
    return data


def _validate_judgment_semantics(judgment: dict) -> dict:
    text = "\n".join([judgment["why_important"], *judgment["decision_reason"], judgment["action"]]).lower()
    if judgment.get("access_status") == "NOT_CONFIRMED":
        positive_access_claims = (
            "一般利用者が利用でき", "一般ユーザーが利用でき", "誰でも利用", "一般提供され",
            "一般利用可能", "利用可能である", "アクセス可能である", "publicly available",
            "generally available", "条件下で提供され", "条件で提供され",
        )
        if any(term.lower() in text for term in positive_access_claims):
            raise TwoPassArticleError("unconfirmed_access_scope_claim")
        forbidden_action = ("PoC", "概念実証", "申請", "導入する", "試す", "利用開始", "実施する")
        if any(word.lower() in judgment["action"].lower() for word in forbidden_action):
            raise TwoPassArticleError("unconfirmed_access_action_escalation")
    unsupported = ("未検証の安全策", "安全策の有効性が未検証", "安全策は未検証", "安全策が未検証")
    if any(term in text for term in unsupported):
        raise TwoPassArticleError("unsupported_safeguard_validation_claim")
    timing = ("評価で安全策が適用された", "評価時に安全策が適用された", "評価中に安全策が適用された", "適用された安全策")
    if any(term in text for term in timing):
        raise TwoPassArticleError("unsupported_safeguard_application_timing_claim")
    return judgment


def validate_hybrid_judgment_text(text: str) -> dict:
    return _validate_judgment_semantics(_parse_judgment_text(text))


def compose_fact_locked_plan(envelope: dict, judgment: dict) -> dict:
    envelope = validate_fact_envelope(envelope)
    judgment = _validate_judgment_semantics(judgment)
    ledger = envelope["fact_ledger"].strip()
    if len(ledger) > PLAN_SCHEMA["properties"]["source_summary"]["maxLength"]:
        raise TwoPassArticleError("fact_ledger_too_long_for_legacy_plan")
    # Fact-bearing fields are deterministic. No model-generated factual prose is accepted here.
    plan = {
        "source_summary": ledger,
        "what": envelope["name"],
        **judgment,
    }
    return validate_plan(plan)


def validate_hybrid_plan_text(text: str, envelope: dict | None = None) -> dict:
    """Compatibility validator. With an envelope, text is judgment-only and gets composed."""
    if envelope is not None:
        return compose_fact_locked_plan(envelope, validate_hybrid_judgment_text(text))
    # Existing saved composed plans remain readable during migration.
    try:
        data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise ValueError("hybrid_plan_json_invalid") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(PLAN_SCHEMA).validate(data)
    return validate_plan(data)


def load_hybrid_plan_report(plan_report_path: str) -> dict:
    report = json.loads(Path(plan_report_path).read_text(encoding="utf-8"))
    if report.get("status") != "PLAN_VALIDATED" or report.get("semantic_plan_validated") is not True:
        raise TwoPassArticleError("hybrid_plan_report_rejected")
    if report.get("provider") != "groq" or report.get("provider_calls") != 1:
        raise TwoPassArticleError("hybrid_plan_provider_contract_invalid")
    if report.get("business_writes") != 0 or report.get("persist_results") is not False:
        raise TwoPassArticleError("hybrid_plan_persistence_contract_invalid")
    plan = report.get("composed_plan")
    if not isinstance(plan, dict):
        # Migration path for previously validated reports.
        try:
            return validate_hybrid_plan_text(report["result"]["text"])
        except (KeyError, TypeError):
            raise TwoPassArticleError("hybrid_plan_result_missing") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(PLAN_SCHEMA).validate(plan)
    return validate_plan(plan)
