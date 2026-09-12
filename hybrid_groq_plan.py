"""Hybrid-only Groq Decision Plan adapter.

The shared Groq strict-schema route remains unchanged for other stages. Decision Plan uses
Groq JSON Object Mode because repeated strict=true calls returned provider-side
json_validate_failed with a short non-JSON failed_generation. Safety is preserved by
validating the returned JSON against the original full PLAN_SCHEMA locally and then applying
validate_plan semantic guards before any Gemini writer call.
"""
from __future__ import annotations

import json
from pathlib import Path

from groq_two_pass_article import PLAN_SCHEMA, build_plan_fixture, validate_plan

MODE = "json_object_local_strict"


def build_hybrid_plan_fixture(input_path: str, output_path: str) -> dict:
    fixture = build_plan_fixture(input_path, output_path)
    exact_keys = ", ".join(PLAN_SCHEMA["required"])
    fixture["structured_output_mode"] = MODE
    # 2026-09-12: same-prompt 3000-token experiment succeeded with 1692 output tokens.
    # Keep this bounded Hybrid setting separate from other Groq stages.
    fixture["max_output_tokens"] = 3000
    fixture["prompt"] = fixture["prompt"].replace(
        "- JSON Schemaに厳密に従いJSONだけを返す。",
        "- JSONオブジェクト1個だけを返す。Markdown、コードフェンス、説明、前置き、後書きは禁止。\n"
        f"- 必須キーは次の16個だけ。すべて1回ずつ含め、余分なキーは禁止: {exact_keys}\n"
        "- decision は NOW / TRY / WATCH / WAIT / AVOID のいずれか。\n"
        "- access_status は CONFIRMED_AVAILABLE / NOT_CONFIRMED / NOT_RELEVANT のいずれか。\n"
        "- business_impact/technical_impact/urgency/market_impact/reliability/article_value は整数。\n"
        "- decision_reason は1〜3個の文字列配列。それ以外の説明項目は文字列。"
    )
    fixture["prompt"] += """

【判断と採点の較正】
- 評価時の設定・アクセス条件は、製品の提供形態ではない。Daybreak Blueはこの資料では評価条件としてだけ扱う。
- 資料が安全策の名称を示すだけなら、有効性も無効性も未確定。「未検証の安全策に依存している」と否定的な事実へ変換しない。
- 利用条件が未確認であることだけを理由にAVOIDへ飛躍しない。WATCH/WAIT/AVOIDは、対象読者と確認済みの採否根拠を区別して決める。根拠のある見送りは妨げない。
- Decision Scoreの上限はbusiness_impact=25、technical_impact=25、urgency=20、market_impact=15、reliability=15。各軸を別々に評価し、利用条件の不明を全軸へ重複減点しない。
- article_valueは0〜100の記事としての価値。導入の可否や安全性とは別に、確認済みの発見が読者へ与える理解と判断材料を評価する。
- 読者は中学生〜非エンジニアも含む。reader_bridgeは読者が理解できる説明の橋渡しを具体化する。「判断のための指針」のような目的説明だけにしない。
"""
    Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def validate_hybrid_plan_text(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("hybrid_plan_empty")
    try:
        data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise ValueError("hybrid_plan_json_invalid") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(PLAN_SCHEMA).validate(data)
    return validate_plan(data)
