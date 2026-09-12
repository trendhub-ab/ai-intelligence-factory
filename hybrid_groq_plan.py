"""Hybrid-only Groq Decision Plan adapter.

The shared Groq strict-schema route remains unchanged for other stages. Decision Plan uses
Groq JSON Object Mode because repeated strict=true calls returned provider-side
json_validate_failed with a short non-JSON failed_generation. Safety is preserved by
validating the returned JSON against the original full PLAN_SCHEMA locally and then applying
Hybrid semantic guards before any Gemini writer call.
"""
from __future__ import annotations

import json
from pathlib import Path

from groq_two_pass_article import PLAN_SCHEMA, build_plan_fixture, validate_plan, TwoPassArticleError

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
- 資料が「公開時に安全策を適用する」と述べる場合、それは公開時の方針であり、評価中に安全策が適用済みだったことを意味しない。「評価で安全策が適用された」「適用された安全策」のように時制・適用範囲を変換しない。「公開時に適用するとされる安全策」までに留める。
- 資料が安全策の名称を示すだけなら、有効性も無効性も未確定。「未検証の安全策」「安全策の有効性が未検証」のように、検証実施の有無まで事実化しない。必要なら「この資料から有効性は確認できない」と書く。
- 利用条件が未確認であることだけを理由にAVOIDへ飛躍しない。WATCH/WAIT/AVOIDは、対象読者と確認済みの採否根拠を区別して決める。根拠のある見送りは妨げない。
- access_status=NOT_CONFIRMEDでも「一般利用者向けに確認できない」のような未確認表現は許可する。一方、「一般利用者が利用できる」「一般提供される」のような提供範囲の肯定断定は禁止する。
- Decision Scoreの上限はbusiness_impact=25、technical_impact=25、urgency=20、market_impact=15、reliability=15。各軸を別々に評価し、利用条件の不明を全軸へ重複減点しない。
- reliabilityは一次情報・測定記述・根拠の信頼性を評価する軸。一般利用可否が未確認であること自体はreliability低下の理由ではない。アクセス不明はaccess_status、decision_reason、actionで表現する。
- business_impact / technical_impact / urgency / market_impact も、アクセス未確認を同じ理由で繰り返し減点しない。確認済みの事実が各軸に与える影響だけを採点する。
- article_valueは0〜100の記事としての価値。導入の可否や安全性とは別に、確認済みの発見が読者へ与える理解と判断材料を評価する。
- 読者は中学生〜非エンジニアも含む。reader_bridgeは読者が理解できる説明の橋渡しを具体化する。「判断のための指針」のような目的説明だけにしない。
"""
    Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def _hybrid_refined_semantic_guard(plan: dict) -> dict:
    """Distinguish uncertainty wording from unsupported access/safeguard claims."""
    legacy_scope_failure = False
    try:
        validate_plan(plan)
    except TwoPassArticleError as exc:
        if str(exc) != "unconfirmed_access_scope_claim":
            raise
        legacy_scope_failure = True

    management_text = "\n".join([
        plan["source_summary"], plan["what"], plan["why_important"],
        *plan["decision_reason"], plan["action"],
    ]).lower()

    if legacy_scope_failure:
        if plan.get("access_status") != "NOT_CONFIRMED":
            raise TwoPassArticleError("unconfirmed_access_scope_claim")
        positive_access_claims = (
            "一般利用者に適用", "一般ユーザーに適用", "一般利用者が利用でき", "一般ユーザーが利用でき",
            "誰でも利用", "一般提供され", "一般提供して", "一般利用可能", "利用可能である",
            "アクセス可能である", "publicly available", "generally available",
            "条件下で提供され", "条件で提供され",
        )
        if any(term.lower() in management_text for term in positive_access_claims):
            raise TwoPassArticleError("unconfirmed_access_scope_claim")

    unsupported_safeguard_assessments = (
        "未検証の安全策", "安全策の有効性が未検証", "安全策は未検証", "安全策が未検証",
    )
    if any(term in management_text for term in unsupported_safeguard_assessments):
        raise TwoPassArticleError("unsupported_safeguard_validation_claim")

    # Migration guard: the current B0049 ledger describes safeguards as publication-time
    # controls. Do not allow the Planner to move them backward into the evaluation itself.
    unsupported_safeguard_timing = (
        "評価で安全策が適用された", "評価時に安全策が適用された", "評価中に安全策が適用された",
        "適用された安全策", "安全策が適用された",
    )
    if any(term in management_text for term in unsupported_safeguard_timing):
        raise TwoPassArticleError("unsupported_safeguard_application_timing_claim")
    return plan


def validate_hybrid_plan_text(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("hybrid_plan_empty")
    try:
        data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise ValueError("hybrid_plan_json_invalid") from None
    from jsonschema import Draft202012Validator
    Draft202012Validator(PLAN_SCHEMA).validate(data)
    return _hybrid_refined_semantic_guard(data)
