"""Run208/341/342/344: bounded Reader Value repair and first-pass Reader Path.

Run208 originally authorized one Reader Value repair only in the Pending Retry fast
lane. The 2026-09-10 real Daily falsified that narrow scope as the sole Production
policy: IBIB passed factual/evidence/publication checks but normal Production stopped
at ``reader_value_review_no_retry``; DeepSeek's mixed HARD retry improved factual
surface while reader-flow scores regressed under the historical local-patch contract.

Run342 replays the failed real manuscripts and tightens only the semantic ordering of
the Reader Path. A rhetorical question or analogy can make prose friendlier without
making the decision easier to reach; therefore reader proximity and decision distance
are treated as different editorial requirements.

Run344 folds the second DeepSeek recovery result back into the same authority. The
article reached Publication Readiness with Gemini 3.6 but still failed Human Appeal and
``LIMITATION_DROPPED``. This falsifies a simple "make it friendlier" strategy: reader
simplification must preserve the practical limit/exception that bounds the decision.
The first-pass contract therefore requires a plain-Japanese limitation bridge and a
small reader payload rather than a larger explanatory surface.

The canonical Reader Value layer owns three bounded responsibilities without relaxing
any gate:
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
ARTICLEは専門知識を見せる順番ではなく、読者が判断できる順番で書く。固定見出しや定型句は使わず、意味の順序だけ守る。
・冒頭3段落以内に必ず、①何が変わった ②それが読者の仕事・利用判断にどう関係する ③現時点の暫定判断（試す／比較する／待つ／見送る等）を置く。結論を最終節まで隠さない。
・冒頭の問いかけや比喩は、それだけではReader Bridgeとみなさない。使うなら直後に「だから何を判断すべきか」まで接続し、問いかけ→説明→比喩→説明だけで冒頭を消費しない。
・最初の専門語・略語は、同じEvidenceの範囲で一度だけ普通の日本語に言い換える。説明のための新事実は足さない。
・冒頭約600文字では、Decisionに不要なAPI名・内部構造・精度名・ベンチマーク条件・実装識別子を並べない。必要な専門語は先に意味、後で名称の順にする。
・高密度な技術説明を2段落続けない。技術説明の次には、その事実が読者の判断をどう変えるかを置く。
・数値は「何の判断に効く数字か」が先に分かるように置く。数字の羅列を先に見せない。ただしEvidence上その数値自体がニュースの核心なら例外とする。
・実装詳細、API名、内部構造、ベンチマーク条件はDecisionに必要なものだけ残し、必要なら暫定判断を示した後へ送る。
・重要な制約・対象範囲・例外・未検証条件がEvidenceにある場合は削らない。専門語をそのまま残すのではなく、「ただし、〜の場合に限る／〜はまだ分からない」のような普通の日本語で1〜2文に圧縮し、暫定判断の直後か、その判断を支える段落内に置く。制約を脚注扱いで最後へ追いやらない。
・読者が前半で覚える中心メッセージは原則3つまでに絞る。①変化 ②判断 ③判断を変えうる重要な制約、を優先し、それ以外の実装詳細や周辺比較は後段へ送る。
・「面白さ」は架空の体験・感情・因果で作らない。比喩を使う場合も事実の代替にせず、Evidenceの意味を平易にする補助に限る。Evidenceの中から意外な差分や判断の分かれ目を1つ選び、そこを記事の軸にする。
・Human Appealは問いかけや比喩の数ではなく、「自分に関係する理由が分かる」「判断が早い」「条件付きでも次に何をするか分かる」で作る。親しみのための前置きは増やさない。
・「私ならどう判断するか」まで待たず、本文前半で暫定判断を示し、終盤では条件・例外・実行手順を精密化する。
・タイトルは日本語として閉じた一文にし、引用符を必ず対応させる。専門語だけのタイトルにしない。
""".strip()

READER_REPAIR_CONTRACT = r"""
【Reader Repair｜Factを固定した読者導線修正】
この修正では新しい調査・新しい事実追加をしない。前稿のFact/Evidenceを正本として、読者導線だけを修正する。
・Evidence URL、一次情報の意味、Decision/Score/Action、根拠付き数値・単位・固有名詞・条件を変えない。
・新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない。
・許可する変更は、タイトル句読点、冒頭と節頭の順序、専門語の平易な言い換え、重複文の削除・統合、判断に不要な実装細部の後送り／削除に限る。
・前稿の後半に既に存在するDecision/Actionを、意味を変えずに冒頭3段落以内へ前倒ししてよい。新しい判断を作ってはいけない。
・冒頭の問いかけ・比喩がDecision到達を遅らせている場合は、削除または1文へ圧縮し、直後に「何が変わった／なぜ関係する／今どうする」を置く。
・冒頭約600文字の専門語・実装識別子は、Decisionに不要なら後段へ移す。意味を落とさず、名称より普通の日本語を先に置く。
・専門語が連続する箇所では、同じEvidenceの意味を普通の日本語で1回だけ橋渡しする。
・数値列挙の前に、その数字が何の判断に効くのかを既存文から前置きする。Evidence条件や単位は削らない。
・前稿にある重要な制約・対象範囲・例外・未検証条件は、平易化のために削除してはいけない。専門語を減らす場合は意味を保った普通の日本語へ置換し、Decisionの直後または同じ判断段落に1〜2文で残す。
・Reader Repair後の前半は、①何が変わった ②今どう判断する ③その判断を変えうる重要な制約、の3点を優先する。問いかけ・比喩・周辺比較よりこの3点を先に置く。
・Human Appealを上げるために導入を長くしない。読者に関係する理由と具体的な次Actionを既存Evidence/Decisionから前へ出す。
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

        # Run341/342 Production finding, folded into this canonical layer to avoid adding
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
    pipeline_module.RUN342_READER_DECISION_DISTANCE = True
    pipeline_module.RUN344_READER_LIMITATION_BRIDGE = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
