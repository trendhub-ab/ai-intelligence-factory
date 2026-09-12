"""Hybrid-only Groq judgment adapter with deterministic Fact Envelope.

Verified evidence is locked before Groq. Groq returns only categorical judgment, scores and
routing codes. It never writes factual prose. The legacy-shaped Decision Plan is composed
locally from the immutable envelope plus deterministic code-to-text mappings.
"""
from __future__ import annotations

import json
from pathlib import Path

from groq_article_parity import load_input
from groq_rate_policy import GPT_OSS_120B, policy_for_model
from groq_two_pass_article import PLAN_SCHEMA, validate_plan, TwoPassArticleError
from hybrid_fact_envelope import build_fact_envelope, validate_fact_envelope

MODE = "json_object_local_strict"

REASON_CODES = (
    "HIGH_TECHNICAL_SIGNIFICANCE",
    "BUSINESS_RELEVANCE",
    "ACCESS_UNCONFIRMED",
    "SAFEGUARD_EFFECTIVENESS_UNCONFIRMED",
    "EVIDENCE_STRONG",
    "EVALUATION_CONDITION_LIMITED",
    "URGENCY_HIGH",
    "MARKET_SIGNAL",
    "NEED_MORE_EVIDENCE",
)
ACTION_CODES = ("CONFIRM_ACCESS", "MONITOR", "COMPARE", "HOLD", "AVOID", "NONE")
READER_PRIORITIES = ("BUSINESS", "TECHNICAL", "SAFETY", "GENERAL")

JUDGMENT_FIELDS = [
    "decision", "reason_codes", "business_impact", "technical_impact", "urgency",
    "market_impact", "reliability", "article_value", "access_status", "action_code",
    "reader_priority",
]
JUDGMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": JUDGMENT_FIELDS,
    "properties": {
        "decision": PLAN_SCHEMA["properties"]["decision"],
        "reason_codes": {
            "type": "array", "minItems": 1, "maxItems": 3, "uniqueItems": True,
            "items": {"enum": list(REASON_CODES)},
        },
        "business_impact": PLAN_SCHEMA["properties"]["business_impact"],
        "technical_impact": PLAN_SCHEMA["properties"]["technical_impact"],
        "urgency": PLAN_SCHEMA["properties"]["urgency"],
        "market_impact": PLAN_SCHEMA["properties"]["market_impact"],
        "reliability": PLAN_SCHEMA["properties"]["reliability"],
        "article_value": PLAN_SCHEMA["properties"]["article_value"],
        "access_status": PLAN_SCHEMA["properties"]["access_status"],
        "action_code": {"enum": list(ACTION_CODES)},
        "reader_priority": {"enum": list(READER_PRIORITIES)},
    },
}

_REASON_TEXT = {
    "HIGH_TECHNICAL_SIGNIFICANCE": "技術的な影響が大きく、継続監視の価値がある。",
    "BUSINESS_RELEVANCE": "事業判断への影響を見極める価値がある。",
    "ACCESS_UNCONFIRMED": "一般利用条件は確認できていない。",
    "SAFEGUARD_EFFECTIVENESS_UNCONFIRMED": "安全策の有効性は、このEvidenceだけでは確認できない。",
    "EVIDENCE_STRONG": "一次情報を中心に根拠を確認できる。",
    "EVALUATION_CONDITION_LIMITED": "評価条件と実運用条件を分けて読む必要がある。",
    "URGENCY_HIGH": "追加情報を待ちつつ、継続的な確認が必要である。",
    "MARKET_SIGNAL": "市場・競争環境への波及を継続監視する価値がある。",
    "NEED_MORE_EVIDENCE": "判断確度を上げるには追加Evidenceが必要である。",
}
_ACTION_TEXT = {
    "CONFIRM_ACCESS": "利用条件を一次情報で確認する。",
    "MONITOR": "追加の一次情報を継続監視する。",
    "COMPARE": "比較可能な一次情報を追加確認する。",
    "HOLD": "追加Evidenceが揃うまで判断を保留する。",
    "AVOID": "現時点では採用を見送る。",
    "NONE": "追加対応は行わず記録のみとする。",
}
_PRIORITY_TEXT = {
    "BUSINESS": (
        "確認済みEvidenceを事業判断へどう結びつけるかが重要である。",
        "確認済みEvidenceが事業判断にどう影響するかを、Factと不確実性を分けて読む。",
        "専門語を減らし、導入判断に必要なFactと未確認事項を分けて説明する。",
        "事業判断のために確認すべきポイント",
    ),
    "TECHNICAL": (
        "確認済みEvidenceの技術的な意味を、評価条件と分けて読む価値がある。",
        "技術的な意味を、確認済みFactと評価条件を混同せずに読む。",
        "専門語を日常語に置き換え、何が確認済みで何が未確認かを分けて説明する。",
        "技術Evidenceから読む次の判断材料",
    ),
    "SAFETY": (
        "能力と安全性の判断を、確認済みEvidenceと未確認事項に分けることが重要である。",
        "安全性を、確認済みFactと未確認事項を混同せずに読む。",
        "危険性を煽らず、確認済みFactと安全性の未確認部分を分けて説明する。",
        "安全性を判断するための確認ポイント",
    ),
    "GENERAL": (
        "確認済みEvidenceから、読者が次に何を確認すべきか整理する価値がある。",
        "確認済みFactと未確認事項を分け、読者の次の判断材料を整理する。",
        "難しい用語を普通の言葉に置き換え、Factと判断を分けて説明する。",
        "確認済みEvidenceから読む次の判断材料",
    ),
}


def build_hybrid_plan_fixture(input_path: str, output_path: str) -> dict:
    item = load_input(input_path)
    envelope = validate_fact_envelope(build_fact_envelope(input_path))
    policy = policy_for_model(GPT_OSS_120B.model)
    exact_keys = ", ".join(JUDGMENT_FIELDS)
    prompt = f"""あなたはAI Intelligence FactoryのDecision Judgeです。
FACT ENVELOPEはプログラムで固定された読み取り専用Evidenceです。
あなたは文章を書きません。確認済みEvidenceを読んで、判断コード・採点・ルーティングコードだけを返します。

【絶対ルール】
- Factの要約、言い換え、説明文、タイトル案、読者向け文章を出力しない。
- FACT ENVELOPEにない事実を推測しない。
- decisionは NOW / TRY / WATCH / WAIT / AVOID。
- reason_codesは次から1〜3個だけ選ぶ: {', '.join(REASON_CODES)}
- access_statusは CONFIRMED_AVAILABLE / NOT_CONFIRMED / NOT_RELEVANT。
- action_codeは次から1個: {', '.join(ACTION_CODES)}
- reader_priorityは次から1個: {', '.join(READER_PRIORITIES)}
- reliabilityはEvidence自体の信頼性。アクセス未確認を重複減点しない。
- business_impact / technical_impact / urgency / market_impact は各軸を独立採点する。
- article_valueは導入可否と別に、記事としての判断材料価値を0〜100で採点する。
- access_status=NOT_CONFIRMEDなら action_code は CONFIRM_ACCESS / MONITOR / HOLD のいずれかにする。
- JSONオブジェクト1個だけを返す。Markdown・説明文・余分なキーは禁止。
- 必須キーは次の11個だけ: {exact_keys}

【候補】
Name: {item['name']}
Screening Score: {item['screening_score']}
Screening Reason: {item['screening_reason']}

【FACT ENVELOPE — READ ONLY】
{json.dumps(envelope, ensure_ascii=False)}
"""
    fixture = {
        "stage": "article", "provider": "groq", "model": GPT_OSS_120B.model,
        "rate_policy": policy.name, "prompt": prompt, "max_output_tokens": 1200,
        "reasoning_effort": "medium", "schema": JUDGMENT_SCHEMA,
        "candidate_id": item["candidate_id"], "pass": "decision_judgment_codes",
        "structured_output_mode": MODE, "fact_envelope": envelope,
        "persist_results": False, "business_writes": 0,
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
    if judgment.get("access_status") == "NOT_CONFIRMED" and judgment.get("action_code") not in {"CONFIRM_ACCESS", "MONITOR", "HOLD"}:
        raise TwoPassArticleError("unconfirmed_access_action_escalation")
    if judgment.get("access_status") == "NOT_CONFIRMED" and "ACCESS_UNCONFIRMED" not in judgment.get("reason_codes", []):
        raise TwoPassArticleError("unconfirmed_access_reason_missing")
    if judgment.get("access_status") == "CONFIRMED_AVAILABLE" and "ACCESS_UNCONFIRMED" in judgment.get("reason_codes", []):
        raise TwoPassArticleError("confirmed_access_reason_conflict")
    return judgment


def validate_hybrid_judgment_text(text: str) -> dict:
    return _validate_judgment_semantics(_parse_judgment_text(text))


def compose_fact_locked_plan(envelope: dict, judgment: dict) -> dict:
    envelope = validate_fact_envelope(envelope)
    judgment = _validate_judgment_semantics(judgment)
    ledger = envelope["fact_ledger"].strip()
    if len(ledger) > PLAN_SCHEMA["properties"]["source_summary"]["maxLength"]:
        raise TwoPassArticleError("fact_ledger_too_long_for_legacy_plan")
    why_important, article_angle, reader_bridge, title_seed_base = _PRIORITY_TEXT[judgment["reader_priority"]]
    reason_texts = [_REASON_TEXT[code] for code in judgment["reason_codes"]]
    title_seed = f"{title_seed_base}：{envelope['name']}"
    if len(title_seed) > PLAN_SCHEMA["properties"]["title_seed"]["maxLength"]:
        title_seed = title_seed_base
    plan = {
        "source_summary": ledger,
        "what": envelope["name"],
        "why_important": why_important,
        "decision": judgment["decision"],
        "decision_reason": reason_texts,
        "business_impact": judgment["business_impact"],
        "technical_impact": judgment["technical_impact"],
        "urgency": judgment["urgency"],
        "market_impact": judgment["market_impact"],
        "reliability": judgment["reliability"],
        "action": _ACTION_TEXT[judgment["action_code"]],
        "article_value": judgment["article_value"],
        "article_angle": article_angle,
        "reader_bridge": reader_bridge,
        "title_seed": title_seed,
        "access_status": judgment["access_status"],
    }
    return validate_plan(plan)


def validate_hybrid_plan_text(text: str, envelope: dict | None = None) -> dict:
    if envelope is not None:
        return compose_fact_locked_plan(envelope, validate_hybrid_judgment_text(text))
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
        try:
            return validate_hybrid_plan_text(report["result"]["text"])
        except (KeyError, TypeError):
            raise TwoPassArticleError("hybrid_plan_result_missing") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(PLAN_SCHEMA).validate(plan)
    return validate_plan(plan)
