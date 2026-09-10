"""Run341: bounded Production Reader Repair lane.

Production evidence from the 2026-09-10 Daily falsified the hypothesis that weak
non-engineer accessibility is primarily a model-capability problem:

* IBIB passed factual/publication checks, but reader-only REVIEW reasons were
  deliberately converted to ``reader_value_review_no_retry`` in normal Production.
* DeepSeek's mixed fact+reader retry improved factual surface while reader scores
  regressed because the historical HARD patch contract forbids broad rewriting.

This overlay does not relax any gate. It changes only two things:
1. generation receives a Reader Path contract before the first provider call;
2. normal new-candidate Production may use the existing one-quality-retry-per-article
   path when Evidence is sufficient and every remaining blocker is a proven
   reader-only accessibility family.

This module creates no retry loop and owns no provider budget. The canonical article
orchestrator's existing one-retry bound plus provider/per-run budgets remain
authoritative. Fact/Evidence/Publication validation still reruns after repair and
Ready remains fail-closed.
"""
from __future__ import annotations

from typing import Any

_INSTALL_FLAG = "_run341_production_reader_repair_installed"
READER_VALUE_MARKER = "reader_value_review:"

_REPAIRABLE_READER_LABELS = (
    "dense_report_cluster",
    "repetitive_insight",
    "multi_axis_reader_weakness",
    "non_engineer_access_failure",
    "final_surface_multi_axis_reader_weakness",
    "final_surface_non_engineer_access_failure",
    "final_surface_title_unbalanced_kagi",
    "final_surface_title_unbalanced_double_kagi",
    "final_surface_summary_jargon_cluster",
    "final_surface_summary_fragment",
)

READER_PATH_CONTRACT = r"""
【Reader Path Contract｜非エンジニアが迷子にならない順序】
ARTICLEは専門知識を見せる順番ではなく、読者が判断できる順番で書く。
・冒頭2〜3文で、専門語を増やさず「何が変わった／なぜ自分に関係する／今どうする」を先に渡す。
・最初の専門語・略語は、同じEvidenceの範囲で一度だけ普通の日本語に言い換える。説明のための新事実は足さない。
・高密度な技術説明を2段落続けない。技術説明の次には、その事実が読者の判断をどう変えるかを置く。
・実装詳細、API名、内部構造、ベンチマーク条件は、Decisionに必要なものだけ残し、必要なら判断を示した後へ送る。
・「面白さ」は架空の体験・感情・比喩で作らない。Evidenceの中から意外な差分や判断の分かれ目を1つ選び、そこを記事の軸にする。
・終盤まで結論を隠さない。Evidenceが許す範囲で、試す／比較する／待つ／見送るの距離感を早めに見せる。
・タイトルは日本語として閉じた一文にし、引用符を必ず対応させる。専門語だけのタイトルにしない。
""".strip()

READER_REPAIR_CONTRACT = r"""
【Run341 Reader Repair｜Factを固定した読者導線修正】
この修正では新しい調査・新しい事実追加をしない。前稿のFact/Evidenceを正本として、読者導線だけを修正する。
・Evidence URL、一次情報の意味、Decision/Score/Action、根拠付き数値・単位・固有名詞・条件を変えない。
・新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない。
・許可する変更は、タイトル句読点、冒頭と節頭の順序、専門語の平易な言い換え、重複文の削除・統合、判断に不要な実装細部の後送り／削除に限る。
・冒頭2〜3文だけで「何が変わった／なぜ関係する／今どうする」が分かるようにする。
・専門語が連続する箇所では、同じEvidenceの意味を普通の日本語で1回だけ橋渡しする。
・記事全体を短くすること自体を目的にしない。Evidenceを落とさず、情報の置き場所を変えて読みやすくする。
・修正後も事実Gate、Evidence Gate、Publication Gate、Reader Gateをすべて再判定し、通らなければReadyにしない。
""".strip()


def _message(row: dict) -> str:
    return str((row or {}).get("message") or (row or {}).get("reason") or "")


def _reader_only_repairable(rows: list[dict], hard_severity: str) -> bool:
    if not rows:
        return False
    saw = False
    for row in rows:
        if str((row or {}).get("severity") or "") == hard_severity:
            return False
        message = _message(row)
        if READER_VALUE_MARKER not in message:
            return False
        if not any(label in message for label in _REPAIRABLE_READER_LABELS):
            return False
        saw = True
    return saw


def _evidence_safe(pipeline_module: Any, evidence_result: dict | None) -> bool:
    if not isinstance(evidence_result, dict):
        return False
    expected = str(getattr(pipeline_module, "EVIDENCE_SUFFICIENT", "SUFFICIENT"))
    return (
        str(evidence_result.get("state") or "") == expected
        and evidence_result.get("decision_scope_safe") is True
    )


def _has_reader_issue(rows: list[dict]) -> bool:
    return any(READER_VALUE_MARKER in _message(row) for row in rows or [])


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original_retry = pipeline_module.should_attempt_dynamic_retry
    original_prompt = pipeline_module.build_decision_prompt
    original_retry_instruction = pipeline_module.build_dynamic_retry_instruction

    def should_attempt_dynamic_retry_with_production_reader_repair(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ) -> tuple[bool, str]:
        allowed, reason = original_retry(reason_rows, evidence_result, candidate_origin)
        if allowed:
            return allowed, reason
        if candidate_origin != "new":
            return allowed, reason
        if reason != "reader_value_review_no_retry":
            return allowed, reason
        if not _evidence_safe(pipeline_module, evidence_result):
            return allowed, reason
        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
        if not _reader_only_repairable(list(reason_rows or []), hard):
            return allowed, reason
        # Authorization only. The existing article orchestration owns the one-retry
        # lifecycle; this wrapper cannot recurse or issue a provider call itself.
        return True, "run341_production_reader_repair"

    def build_decision_prompt_with_reader_path(*args: Any, **kwargs: Any) -> str:
        prompt = str(original_prompt(*args, **kwargs) or "")
        return prompt.rstrip() + "\n\n" + READER_PATH_CONTRACT + "\n"

    def build_dynamic_retry_instruction_with_reader_repair(reason_rows: list[dict]):
        instruction, sections = original_retry_instruction(reason_rows)
        if _has_reader_issue(list(reason_rows or [])):
            instruction = str(instruction).rstrip() + "\n\n" + READER_REPAIR_CONTRACT
        return instruction, sections

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_production_reader_repair
    pipeline_module.build_decision_prompt = build_decision_prompt_with_reader_path
    pipeline_module.build_dynamic_retry_instruction = build_dynamic_retry_instruction_with_reader_repair
    pipeline_module.RUN341_PRODUCTION_READER_REPAIR = True
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
