"""Run171 Production Yield Guardrails + Run169 Reader Value Review Bridge.

This module remains an installable editorial layer, but its standalone entrypoint is no longer
an independent production stack.  Direct execution delegates to production_pipeline.main so
manual/regression callers cannot accidentally run only Run172 + the historical reader bridge
while bypassing later fact, eyecatch, funnel, and publication-integrity layers.
"""
from __future__ import annotations

from typing import Any

READER_VALUE_MARKER = "reader_value_review:"
_INSTALLED_ATTR = "_run169_reader_value_review_bridge_installed"


PRODUCTION_YIELD_CONTRACT = r"""
【Production Yield Consistency Contract｜最終セルフチェック】
出力直前に、ARTICLEへ新しい情報を足さず、次の4点だけを必ず照合する。

1. Decision整合
・MANAGEMENT DATAの Decision / Decision Reason / Decision Score / Action と、ARTICLE終盤の判断は同じ「行動までの距離」を示す。
・DecisionとScoreを別々に楽観・悲観評価しない。EvidenceからDecisionを決め、その意味と矛盾しないScore・Action・結論にする。
・WATCH / WAIT / AVOIDなのに「今すぐ」「直ちに」「全面導入」「必ず導入」と急がせない。低いUrgencyを付けたのに本文だけ緊急化しない。
・NOW / TRYでもEvidenceが限定的なら、対象範囲・検証条件を残し、全面展開へ飛躍しない。

2. 数値・固有名詞のSource Boundary
・ARTICLEに出す数値、割合、期間、人数、性能値、金額、固有の人物名、技術名、API名、パッケージ名は、Source Native Context / Structured Evidence / Freshness Resolutionのいずれかで直接確認できるものだけにする。
・「数年」「数倍」「2分」のような曖昧・日本語化された数量表現も数値Claimとして扱う。根拠がなければ書かない。
・判断に不要な数字や固有名詞は、モデル内部知識で補わず省く。分からない具体性を足して記事を賢く見せない。

3. One Insight, One Home
・同じ核心事実・洞察を、別の見出しで言い換えて二度三度説明しない。主要な説明は最も自然な1箇所に置く。
・後段で必要なら同じ説明を繰り返さず、「その結果、読者の判断に何が変わるか」へ進める。
・同じ7文字以上の特徴的な言い回しを複数段落へ反復しない。ただし正式な技術名・不可欠なEvidence表記は除く。

4. Decision Voice
・終盤には、架空の使用経験や感情ではなく、取得済みEvidenceに基づく編集者自身の判断を最低1文置く。
・「私なら、この条件では小さく試す」「私なら今は導入を急がない」のように、試す／比較する／待つ／見送る等の具体的な距離感を示す。表現は記事ごとに自然に変える。
・「注視したい」「今後を見たい」だけで終わらず、読者が次に何をするかまで分かるActionへつなげる。

上の照合で矛盾が見つかった場合は、Evidence・事実・重要制約を変えず、Decision/Score/Action/結論または重複表現だけを最小限修正してから出力する。
""".strip()


def _material_reader_value_issues(pipeline_module: Any, article: str) -> list[str]:
    """Return only high-confidence reader-value failures from existing 0-API signals."""
    if not article:
        return []
    signals = pipeline_module._reader_experience_signals(article)
    issues: list[str] = []
    dense_report_cluster = all(
        signals.get(key) == "REVIEW"
        for key in (
            "reader_enjoyment",
            "narrative_pull",
            "information_budget",
            "reader_temperature_rhythm",
        )
    )
    if dense_report_cluster:
        issues.append(
            READER_VALUE_MARKER
            + "dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"
        )
    severe_flags = (
        ("warm_hook_cold_body", "warm_hook_cold_body"),
        ("analogy_substance_thin", "analogy_substance_thin"),
        ("reader_delight_overclaim", "reader_delight_overclaim"),
        ("repetitive_insight", "repetitive_insight"),
    )
    for key, label in severe_flags:
        if bool(signals.get(key)):
            issues.append(READER_VALUE_MARKER + label)
    return list(dict.fromkeys(issues))


def _row_is_reader_value(row: dict) -> bool:
    message = str(row.get("message") or row.get("reason") or "")
    return READER_VALUE_MARKER in message


def _retry_yield_guardrails(pipeline_module: Any, reason_rows: list[dict]) -> str:
    """Return local repair guidance only for failure classes actually present."""
    rows = list(reason_rows or [])
    codes = {str(row.get("reason_code") or "") for row in rows}
    messages = "\n".join(str(row.get("message") or row.get("reason") or "") for row in rows)
    additions: list[str] = []

    if getattr(pipeline_module, "REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH", "") in codes or "score_narrative_mismatch" in messages:
        additions.append(
            "Decision整合修正では、既存のMANAGEMENT DATAのDecision・Decision Score・Decision Reason・Actionと"
            "ARTICLE終盤の判断を同じ行動距離へそろえてください。Evidenceやスコア根拠は作り替えず、"
            "矛盾する緊急度表現・結論・Actionだけを局所修正してください。"
        )
    if getattr(pipeline_module, "REASON_CODE_APPEAL_DECISION_VOICE_LOSS", "") in codes or "decision_voice_missing" in messages:
        additions.append(
            "Decision Voice修正では、架空の経験・感情を追加せず、既存Evidenceから導ける編集者自身の判断を1文だけ復元し、"
            "限定検証・比較・待機・見送り等の具体的な次Actionへ接続してください。『注視する』だけへの置換は禁止です。"
        )
    if "repetitive_insight" in messages:
        additions.append(
            "反復修正では、同じ核心事実・洞察を説明している重複文を削除または1箇所へ統合してください。"
            "新しい説明や比喩を足さず、後段は同じ説明の言い換えではなく、その事実が判断に与える意味へ進めてください。"
        )
    if "dense_report_cluster" in messages:
        additions.append(
            "Dense report修正では、Evidence・数値・制約を削らず、重複説明・汎用前置き・Decisionに不要な実装列挙だけを"
            "削除または平易な1文へ置換してください。記事全体の再構成や新事実の追加はしないでください。"
        )
    if not additions:
        return ""
    return "\n".join(["【Run171 局所修正ガード】", *["・" + item for item in additions]])


def install(pipeline_module: Any) -> Any:
    """Install the historical reader-value policy bridge idempotently."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_human_appeal = pipeline_module.validate_human_appeal_gate
    original_retry_policy = pipeline_module.should_attempt_dynamic_retry
    original_build_prompt = pipeline_module.build_decision_prompt
    original_build_retry_instruction = pipeline_module.build_dynamic_retry_instruction

    def validate_human_appeal_gate_with_reader_value(parsed: dict, peer_articles=None):
        state, issues = original_human_appeal(parsed, peer_articles)
        issues = list(issues or [])
        reader_issues = _material_reader_value_issues(
            pipeline_module,
            str((parsed or {}).get("note_draft") or ""),
        )
        if reader_issues:
            issues.extend(x for x in reader_issues if x not in issues)
            if state == "ACCEPTABLE":
                state = "WEAK"
        return state, issues

    def should_attempt_dynamic_retry_without_reader_only_spend(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        rows = list(reason_rows or [])
        reader_rows = [row for row in rows if _row_is_reader_value(row)]
        if reader_rows:
            non_reader_blocking = [
                row
                for row in rows
                if not _row_is_reader_value(row)
                and row.get("severity")
                in {
                    getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"),
                    getattr(pipeline_module, "GATE_SEVERITY_REVIEW", "REVIEW"),
                }
            ]
            if not non_reader_blocking:
                return False, "reader_value_review_no_retry"
        return original_retry_policy(rows, evidence_result, candidate_origin)

    def build_decision_prompt_with_yield_guardrails(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        return prompt.rstrip() + "\n\n" + PRODUCTION_YIELD_CONTRACT + "\n"

    def build_dynamic_retry_instruction_with_yield_guardrails(reason_rows: list[dict]):
        instruction, sections = original_build_retry_instruction(reason_rows)
        extra = _retry_yield_guardrails(pipeline_module, reason_rows)
        if extra:
            instruction = instruction.rstrip() + "\n" + extra
        return instruction, sections

    pipeline_module.validate_human_appeal_gate = validate_human_appeal_gate_with_reader_value
    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_without_reader_only_spend
    pipeline_module.build_decision_prompt = build_decision_prompt_with_yield_guardrails
    pipeline_module.build_dynamic_retry_instruction = build_dynamic_retry_instruction_with_yield_guardrails
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module


def main() -> None:
    # Historical direct execution used to install only Run172 + this bridge and therefore
    # silently bypassed later production layers.  There is now exactly one production stack.
    import production_pipeline

    production_pipeline.main()


if __name__ == "__main__":
    main()
