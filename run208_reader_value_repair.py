"""Run208/341: bounded Reader Value repair and first-pass Reader Path.

Run208 originally authorized one Reader Value repair only in the Pending Retry fast
lane. The 2026-09-10 real Daily falsified that narrow scope as the sole Production
policy: IBIB passed factual/evidence/publication checks but normal Production stopped
at ``reader_value_review_no_retry``; DeepSeek's mixed HARD retry improved factual
surface while reader-flow scores regressed under the historical local-patch contract.

The canonical Reader Value layer now owns three bounded responsibilities without
relaxing any gate:
1. add a first-pass Reader Path contract before generation;
2. preserve the historical one-spend Pending Retry fast-lane repair;
3. allow fresh Production reader-only accessibility failures to use the article
   orchestrator's existing one-quality-retry-per-article path when Evidence is
   SUFFICIENT and decision scope is safe.

It creates no provider loop and no new request budget. Fact/Evidence/Publication/
Reader gates still rerun after repair and remain fail-closed.
"""
from __future__ import annotations

import os
from typing import Any

FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"
_INSTALLED_ATTR = "_run208_reader_value_repair_installed"
_SPENT_ATTR = "_run208_reader_value_repair_spent"
READER_VALUE_MARKER = "reader_value_review:"
_PENDING_REPAIRABLE = ("dense_report_cluster", "repetitive_insight")
_FRESH_REPAIRABLE = (
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
・実装詳細、API名、内部構造、ベンチマーク条件はDecisionに必要なものだけ残し、必要なら判断を示した後へ送る。
・「面白さ」は架空の体験・感情・比喩で作らない。Evidenceの中から意外な差分や判断の分かれ目を1つ選び、そこを記事の軸にする。
・終盤まで結論を隠さない。Evidenceが許す範囲で、試す／比較する／待つ／見送るの距離感を早めに見せる。
・タイトルは日本語として閉じた一文にし、引用符を必ず対応させる。専門語だけのタイトルにしない。
""".strip()

READER_REPAIR_CONTRACT = r"""
【Reader Repair｜Factを固定した読者導線修正】
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


def _reader_only_repairable(rows: list[dict], labels: tuple[str, ...], hard_severity: str | None = None) -> bool:
    if not rows:
        return False
    for row in rows:
        if hard_severity and str((row or {}).get("severity") or "") == hard_severity:
            return False
        message = _message(row)
        if READER_VALUE_MARKER not in message:
            return False
        if not any(label in message for label in labels):
            return False
    return True


def _fresh_evidence_safe(pipeline_module: Any, evidence_result: dict | None) -> bool:
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
    """Install canonical Reader Value policy idempotently."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_retry = pipeline_module.should_attempt_dynamic_retry
    original_prompt = pipeline_module.build_decision_prompt
    original_retry_instruction = pipeline_module.build_dynamic_retry_instruction
    setattr(pipeline_module, _SPENT_ATTR, False)

    def should_attempt_dynamic_retry_with_reader_repair(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        allowed, reason = original_retry(reason_rows, evidence_result, candidate_origin)
        if allowed:
            return allowed, reason
        if reason != "reader_value_review_no_retry":
            return allowed, reason

        rows = list(reason_rows or [])

        # Historical Run208 fast lane: one process-local spend only. Existing provider,
        # per-run and Pending Retry budgets remain authoritative.
        if (
            os.getenv(FAST_LANE_ENV, "") == "1"
            and candidate_origin == "pending_retry"
            and evidence_result is not None
            and not getattr(pipeline_module, _SPENT_ATTR, False)
            and _reader_only_repairable(rows, _PENDING_REPAIRABLE)
        ):
            setattr(pipeline_module, _SPENT_ATTR, True)
            return True, "run208_reader_value_fast_lane_repair"

        # Run341 Production finding, folded into this canonical layer to avoid adding
        # another permanent runtime wrapper. Authorization only: the article lifecycle
        # already permits at most one quality retry for this candidate.
        if candidate_origin == "new" and _fresh_evidence_safe(pipeline_module, evidence_result):
            hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
            if _reader_only_repairable(rows, _FRESH_REPAIRABLE, hard):
                return True, "run341_production_reader_repair"

        return allowed, reason

    def build_decision_prompt_with_reader_path(*args: Any, **kwargs: Any) -> str:
        prompt = str(original_prompt(*args, **kwargs) or "")
        return prompt.rstrip() + "\n\n" + READER_PATH_CONTRACT + "\n"

    def build_dynamic_retry_instruction_with_reader_repair(reason_rows: list[dict]):
        instruction, sections = original_retry_instruction(reason_rows)
        if _has_reader_issue(list(reason_rows or [])):
            instruction = str(instruction).rstrip() + "\n\n" + READER_REPAIR_CONTRACT
        return instruction, sections

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_reader_repair
    pipeline_module.build_decision_prompt = build_decision_prompt_with_reader_path
    pipeline_module.build_dynamic_retry_instruction = build_dynamic_retry_instruction_with_reader_repair
    pipeline_module.RUN341_PRODUCTION_READER_REPAIR = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
