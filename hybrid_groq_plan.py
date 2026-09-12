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
    fixture["prompt"] = fixture["prompt"].replace(
        "- JSON Schemaに厳密に従いJSONだけを返す。",
        "- JSONオブジェクト1個だけを返す。Markdown、コードフェンス、説明、前置き、後書きは禁止。\n"
        f"- 必須キーは次の16個だけ。すべて1回ずつ含め、余分なキーは禁止: {exact_keys}\n"
        "- decision は NOW / TRY / WATCH / WAIT / AVOID のいずれか。\n"
        "- access_status は CONFIRMED_AVAILABLE / NOT_CONFIRMED / NOT_RELEVANT のいずれか。\n"
        "- business_impact/technical_impact/urgency/market_impact/reliability/article_value は整数。\n"
        "- decision_reason は1〜3個の文字列配列。それ以外の説明項目は文字列。"
    )
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
