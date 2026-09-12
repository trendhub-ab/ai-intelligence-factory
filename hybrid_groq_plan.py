"""Hybrid-only Groq judgment adapter with deterministic Fact Envelope.

Verified evidence is locked before Groq. Groq returns only categorical judgment, scores and
routing codes. It never writes factual prose. The Decision Plan stores only a deterministic
reference to the immutable Fact Envelope; the full evidence ledger stays outside legacy
source_summary limits and remains available from the writer input/snapshot.
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


def _fact_envelope_reference(envelope: dict) -> str:
    """Return a short deterministic legacy-compatible pointer, never a truncated fact."""
    digest = str(envelope["fact_ledger_sha256"])
    return f"Fact Envelope参照（SHA256:{digest}）。本文の事実根拠は固定Evidenceを使用する。"


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
- access_status=NOT_CONFIRMEDなら action_code は CONFIRM_ACCESS / MONITOR / HOLD のいずれかにする。reason_codesにACCESS_UNCONFIRMEDを必須化しない。アクセス状態はプログラム側でDecision Reasonへ確実に反映する。

【Decision Score較正】
各軸は他軸と独立して採点し、同じ不確実性を複数軸で重複減点しない。
- business_impact 0〜25: 0=事業影響なし、5=ごく限定的、10=一部の実務に意味、15=明確な事業判断材料、20=複数業務や競争力へ大きな影響、25=広範かつ即時の事業インパクト。アクセス未確認だけで下げない。
- technical_impact 0〜25: 0=技術的新規性なし、5=小改善、10=有用な改善、15=明確な技術的前進、20=フロンティア級または大きな能力変化、25=技術前提を変える級。一次資料が能力閾値・大幅な評価結果・新しい能力を示す場合は高得点を検討する。
- urgency 0〜20: 0=対応不要、5=長期監視、10=近い将来の確認が必要、15=短期で判断材料を更新すべき、20=即時対応が必要。利用可否が未確認という理由だけで0近辺にしない。
- market_impact 0〜15: 0=市場影響なし、5=ニッチ、10=業界・競争環境に意味、15=広い市場構造へ強い影響。提供条件未確認と市場インパクトは別軸。
- reliability 0〜15: 0=根拠なし、5=限定的な二次情報、10=一次情報だが条件・測定に留意、13=一次情報で具体的な測定・条件・数値が確認できる、15=複数の強い独立根拠または極めて明確な一次Evidence。一般利用可否が不明でも一次Evidenceの信頼性は下げない。
- totalは上記5軸の合計0〜100。高い技術的・事業的価値と、アクセス未確認は同時に成立し得る。
- article_valueはDecision Scoreと別。読者がFact・条件・意味を理解する価値が高ければ、導入を待つ判断でも高くできる。

【Decision較正】
- NOW/TRYは、実際の利用・行動へ進める根拠が確認できる場合。
- WATCHは、価値が高く追うべきだが、提供条件や追加Evidence待ちの場合。
- WAITは、現時点で行動根拠が不足し、追加Evidence待ちが主判断の場合。
- AVOIDは、確認済みEvidenceに見送り根拠がある場合。アクセス未確認だけでAVOIDにしない。
- 高いDecision ScoreだからNOWとは限らず、ScoreとDecisionを分離する。

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
    if judgment.get("access_status") == "CONFIRMED_AVAILABLE" and "ACCESS_UNCONFIRMED" in judgment.get("reason_codes", []):
        raise TwoPassArticleError("confirmed_access_reason_conflict")
    return judgment


def validate_hybrid_judgment_text(text: str) -> dict:
    return _validate_judgment_semantics(_parse_judgment_text(text))


def compose_fact_locked_plan(envelope: dict, judgment: dict) -> dict:
    envelope = validate_fact_envelope(envelope)
    judgment = _validate_judgment_semantics(judgment)
    why_important, article_angle, reader_bridge, title_seed_base = _PRIORITY_TEXT[judgment["reader_priority"]]
    reason_codes = list(judgment["reason_codes"])
    if judgment["access_status"] == "NOT_CONFIRMED" and "ACCESS_UNCONFIRMED" not in reason_codes:
        reason_codes = reason_codes[:2] + ["ACCESS_UNCONFIRMED"]
    reason_texts = [_REASON_TEXT[code] for code in reason_codes]
    title_seed = f"{title_seed_base}：{envelope['name']}"
    if len(title_seed) > PLAN_SCHEMA["properties"]["title_seed"]["maxLength"]:
        title_seed = title_seed_base
    plan = {
        "source_summary": _fact_envelope_reference(envelope),
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
