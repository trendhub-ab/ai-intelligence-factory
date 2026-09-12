"""Groq-only two-pass article adapter.

This module does not modify or install into Gemini Production. It decouples structured
Decision/management planning from prose writing so list-oriented management output cannot
prime the article body. Both stages are fail-closed and business-write free.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from groq_article_parity import load_input
from groq_rate_policy import GPT_OSS_120B, COMPOUND_MINI, policy_for_model


class TwoPassArticleError(RuntimeError):
    pass


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source_summary", "what", "why_important", "decision", "decision_reason",
        "business_impact", "technical_impact", "urgency", "market_impact", "reliability",
        "action", "article_value", "article_angle", "reader_bridge", "title_seed",
        "access_status",
    ],
    "properties": {
        "source_summary": {"type": "string", "minLength": 1, "maxLength": 500},
        "what": {"type": "string", "minLength": 1, "maxLength": 500},
        "why_important": {"type": "string", "minLength": 1, "maxLength": 500},
        "decision": {"enum": ["NOW", "TRY", "WATCH", "WAIT", "AVOID"]},
        "decision_reason": {
            "type": "array", "minItems": 1, "maxItems": 3,
            "items": {"type": "string", "minLength": 1, "maxLength": 240},
        },
        "business_impact": {"type": "integer", "minimum": 0, "maximum": 25},
        "technical_impact": {"type": "integer", "minimum": 0, "maximum": 25},
        "urgency": {"type": "integer", "minimum": 0, "maximum": 20},
        "market_impact": {"type": "integer", "minimum": 0, "maximum": 15},
        "reliability": {"type": "integer", "minimum": 0, "maximum": 15},
        "action": {"type": "string", "minLength": 1, "maxLength": 400},
        "article_value": {"type": "integer", "minimum": 0, "maximum": 100},
        "article_angle": {"type": "string", "minLength": 1, "maxLength": 240},
        "reader_bridge": {"type": "string", "minLength": 1, "maxLength": 300},
        "title_seed": {"type": "string", "minLength": 1, "maxLength": 160},
        "access_status": {"enum": ["CONFIRMED_AVAILABLE", "NOT_CONFIRMED", "NOT_RELEVANT"]},
    },
}


def _dump(path: str, value: dict) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _result_text(report: dict) -> str:
    try:
        text = report["result"]["text"]
    except (KeyError, TypeError):
        raise TwoPassArticleError("provider_result_missing") from None
    if not isinstance(text, str) or not text.strip():
        raise TwoPassArticleError("provider_result_empty")
    return text.strip()


def _contains_japanese(text: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ヶ一-龯]", text or ""))


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise TwoPassArticleError("plan_not_object")
    required = set(PLAN_SCHEMA["required"])
    if set(plan) != required:
        raise TwoPassArticleError("plan_shape_mismatch")
    if plan["decision"] not in {"NOW", "TRY", "WATCH", "WAIT", "AVOID"}:
        raise TwoPassArticleError("plan_decision_invalid")
    if plan["access_status"] not in {"CONFIRMED_AVAILABLE", "NOT_CONFIRMED", "NOT_RELEVANT"}:
        raise TwoPassArticleError("plan_access_status_invalid")
    limits = {
        "business_impact": 25, "technical_impact": 25, "urgency": 20,
        "market_impact": 15, "reliability": 15, "article_value": 100,
    }
    for key, upper in limits.items():
        value = plan.get(key)
        if type(value) is not int or not 0 <= value <= upper:
            raise TwoPassArticleError("plan_score_invalid:" + key)
    reasons = plan.get("decision_reason")
    if (not isinstance(reasons, list) or not 1 <= len(reasons) <= 3
            or any(not isinstance(x, str) or not x.strip() or len(x) > 240 for x in reasons)):
        raise TwoPassArticleError("plan_reasons_invalid")
    text_limits = {
        "source_summary": 500, "what": 500, "why_important": 500, "action": 400,
        "article_angle": 240, "reader_bridge": 300, "title_seed": 160,
    }
    for key, upper in text_limits.items():
        value = plan.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > upper:
            raise TwoPassArticleError("plan_text_invalid:" + key)
    for key in ("article_angle", "reader_bridge", "title_seed"):
        if not _contains_japanese(plan[key]):
            raise TwoPassArticleError("plan_editorial_seed_not_japanese:" + key)
    if plan["access_status"] == "NOT_CONFIRMED":
        forbidden_action = ("PoC", "概念実証", "申請", "導入する", "試す", "利用開始", "実施する")
        if any(word in plan["action"] for word in forbidden_action):
            raise TwoPassArticleError("unconfirmed_access_action_escalation")
        unknown_scope = (
            "一般利用者", "一般ユーザー", "誰でも利用", "一般提供", "利用可能",
            "アクセス可能", "publicly available", "generally available",
            "条件下で提供され", "条件で提供され",
        )
        management_text = "\n".join([
            plan["source_summary"], plan["what"], plan["why_important"],
            *plan["decision_reason"], plan["action"],
        ]).lower()
        if any(term.lower() in management_text for term in unknown_scope):
            raise TwoPassArticleError("unconfirmed_access_scope_claim")
    return plan


def build_plan_fixture(input_path: str, output_path: str) -> dict:
    item = load_input(input_path)
    policy = policy_for_model(GPT_OSS_120B.model)
    prompt = f"""あなたはAI Intelligence FactoryのDecision Plannerです。
これはGroq移行検証専用です。以下のALLOWED FACT LEDGER以外を事実として追加してはいけません。

【絶対ルール】
- 数値は対象・条件と一体で扱う。100%等を一般性能へ拡張しない。
- 評価条件を提供条件、安全策の適用範囲、一般利用可否へ横滑りさせない。
- 安全策の名称から機能、リアルタイム性、ログ、保証を推測しない。
- アクセス可否が一次情報で確認できない場合 access_status=NOT_CONFIRMED とし、Actionは条件確認まで。PoC、申請、導入、試用を勧めない。
- access_status=NOT_CONFIRMEDなら、「一般利用者に適用」「一般提供」「誰でも利用可能」などアクセス範囲を断定する表現を、Source Summary / What / Why Important / Decision Reason / Actionのどこにも書かない。
- why_importantは実務上の意味だが、未検証効果を事実にしない。
- article_angle / reader_bridge / title_seedは編集案であり、新しいFactを含めない。3項目は必ず自然な日本語で書く。
- JSON Schemaに厳密に従いJSONだけを返す。

【候補】
Name: {item['name']}
Primary URL: {item['url']}
Screening Score: {item['screening_score']}
Screening Reason: {item['screening_reason']}

【ALLOWED FACT LEDGER】
{item['source_context']}
"""
    fixture = {
        "stage": "article",
        "provider": "groq",
        "model": GPT_OSS_120B.model,
        "rate_policy": policy.name,
        "prompt": prompt,
        "max_output_tokens": 1100,
        "reasoning_effort": "medium",
        "schema": PLAN_SCHEMA,
        "candidate_id": item["candidate_id"],
        "pass": "decision_plan",
        "persist_results": False,
        "business_writes": 0,
    }
    _dump(output_path, fixture)
    return fixture


def load_plan_report(plan_report_path: str) -> dict:
    report = json.loads(Path(plan_report_path).read_text(encoding="utf-8"))
    if report.get("status") == "PLAN_REJECTED" or report.get("semantic_plan_validated") is False:
        raise TwoPassArticleError("plan_report_rejected")
    if report.get("provider") != "groq" or report.get("provider_calls") != 1:
        raise TwoPassArticleError("plan_provider_contract_invalid")
    try:
        plan = json.loads(_result_text(report))
    except json.JSONDecodeError:
        raise TwoPassArticleError("plan_json_invalid") from None
    return validate_plan(plan)


def build_writer_fixture(input_path: str, plan_report_path: str, output_path: str) -> dict:
    item = load_input(input_path)
    plan = load_plan_report(plan_report_path)
    policy = policy_for_model(COMPOUND_MINI.model)
    plan_for_writer = {
        "decision": plan["decision"],
        "article_angle": plan["article_angle"],
        "reader_bridge": plan["reader_bridge"],
        "title_seed": plan["title_seed"],
        "action": plan["action"],
        "access_status": plan["access_status"],
    }
    prompt = f"""あなたはAI Intelligence Factoryの日本語テック編集者です。
今回は記事本文だけを書きます。管理データや箇条書き帳票は出力しません。

【ALLOWED FACT LEDGER — 事実の上限】
{item['source_context']}

【EDITORIAL PLAN — 事実ソースではない】
{json.dumps(plan_for_writer, ensure_ascii=False)}

【執筆契約】
- Ledgerにない固有名詞、機能、アクセス条件、価格、比較、現在仕様、効果を追加しない。
- 数値はLedgerにある測定対象・条件と同じ文脈でのみ使う。100%を一般性能へ広げない。
- 安全策はLedgerに書かれた名称以上の機能を推測しない。「リアルタイム」「ログ収集」「認証方式」等を足さない。
- 特定configuration/access条件の限定を、別の安全策や一般提供条件へ移さない。
- access_statusがNOT_CONFIRMEDなら、申請・PoC・試用・導入を勧めず「利用条件を一次情報で確認する」までにする。
- 中学生〜非エンジニアが読める日本語。専門語は最初に出すとき、同じ文か直後で普通の言葉に言い換える。
- 冒頭は発表要約ではなく、Ledger中の最も驚く事実を1つ使い、最初の3段落以内に「簡単に言えば／たとえば／使う側から見ると」に相当する自然な橋渡しを1回だけ置く。
- Markdownの箇条書き・番号リストは禁止。説明は自然な段落で書く。
- 見出しは2〜4個。記事固有の日本語にし、「何が起きた」「なぜ重要」「仕組み」「リスク」「次にすべきこと」「最終判断」等の汎用ラベルをそのまま見出しにしない。
- 各節を同じ長さ・同じ型にそろえない。90字以上の説明段落を3つ連続させない。
- 煽らない。面白さはLedgerにある意外性と、読者の判断が変わる点から作る。
- 最後はDecisionコードを書かず、Planのdecision/actionと矛盾しない人間の言葉の判断で閉じる。
- 1500〜2600日本語文字を目安にする。Evidence不足なら無理に長くしない。

【出力形式】
必ず次の2つだけを返す。
===TITLE===
記事タイトル（#なし。「。」または「？」で終える）
===ARTICLE===
本文
"""
    fixture = {
        "stage": "article",
        "provider": "groq",
        "model": COMPOUND_MINI.model,
        "rate_policy": policy.name,
        "prompt": prompt,
        "max_output_tokens": 3200,
        "reasoning_effort": "medium",
        "schema": None,
        "candidate_id": item["candidate_id"],
        "pass": "article_writer",
        "persist_results": False,
        "business_writes": 0,
    }
    _dump(output_path, fixture)
    return fixture


def parse_writer_report(writer_report_path: str) -> tuple[str, str, dict]:
    report = json.loads(Path(writer_report_path).read_text(encoding="utf-8"))
    if report.get("provider") != "groq" or report.get("provider_calls") != 1:
        raise TwoPassArticleError("writer_provider_contract_invalid")
    text = _result_text(report)
    match = re.fullmatch(r"\s*===TITLE===\s*\n(.+?)\n===ARTICLE===\s*\n(.+)\s*", text, re.S)
    if not match:
        raise TwoPassArticleError("writer_output_format_invalid")
    title, article = match.group(1).strip(), match.group(2).strip()
    if "\n- " in article or re.search(r"(?m)^\s*\d+[.)]\s+", article):
        raise TwoPassArticleError("writer_list_output_forbidden")
    if not title.endswith(("。", "？")):
        raise TwoPassArticleError("writer_title_punctuation_invalid")
    if len(article) < 800:
        raise TwoPassArticleError("writer_article_too_short")
    return title, article, report


def assemble_combined_report(plan_report_path: str, writer_report_path: str, output_path: str) -> dict:
    plan_report = json.loads(Path(plan_report_path).read_text(encoding="utf-8"))
    plan = load_plan_report(plan_report_path)
    title, article, writer_report = parse_writer_report(writer_report_path)
    total_score = sum(plan[k] for k in ("business_impact", "technical_impact", "urgency", "market_impact", "reliability"))
    management = "\n".join([
        "=== MANAGEMENT DATA ===",
        f"・Source Summary: {plan['source_summary']}",
        f"・What: {plan['what']}",
        f"・Why Important: {plan['why_important']}",
        f"・Decision: {plan['decision']}",
        "・Decision Reason: " + " / ".join(plan["decision_reason"]),
        ("・Decision Score: "
         f"Business Impact {plan['business_impact']}/25; Technical Impact {plan['technical_impact']}/25; "
         f"Urgency {plan['urgency']}/20; Market Impact {plan['market_impact']}/15; "
         f"Reliability {plan['reliability']}/15; 合計 {total_score}/100"),
        f"・Action: {plan['action']}",
        f"・Article Value: {plan['article_value']}",
        "",
        "===SECTION_SPLIT_TOKEN===",
        "",
        "===NOTE_DRAFT_START===",
        title,
        article,
    ])
    plan_result = plan_report.get("result") or {}
    writer_result = writer_report.get("result") or {}
    combined = {
        "mode": "groq_two_pass_article",
        "provider": "groq",
        "model": f"{plan_report.get('model')} + {writer_report.get('model')}",
        "provider_calls": int(plan_report.get("provider_calls", 0)) + int(writer_report.get("provider_calls", 0)),
        "business_writes": 0,
        "quality_validated": False,
        "result": {
            "text": management,
            "provider": "groq",
            "model": f"{plan_report.get('model')} + {writer_report.get('model')}",
            "prompt_tokens": int(plan_result.get("prompt_tokens", 0)) + int(writer_result.get("prompt_tokens", 0)),
            "completion_tokens": int(plan_result.get("completion_tokens", 0)) + int(writer_result.get("completion_tokens", 0)),
        },
        "passes": {
            "plan_model": plan_report.get("model"),
            "writer_model": writer_report.get("model"),
            "access_status": plan["access_status"],
        },
    }
    _dump(output_path, combined)
    return combined
