"""Run208/341/342/344/345: bounded Reader Value repair and first-pass Reader Path.

Run208 originally authorized one Reader Value repair only in the Pending Retry fast
lane. The 2026-09-10 real Daily falsified that narrow scope as the sole Production
policy: reader-only failures need the existing per-article retry when Evidence is safe.
Run342 moved Decision closer to the reader. Run344 preserved limitations while
simplifying.

Run345 uses the real Run41 manuscripts to falsify the next hypothesis: more Reader
instructions do not solve the problem. The base prompt already required 2-3 concepts,
plain-language bridges and reader proximity, yet three unrelated articles still became
jargon-heavy. The missing authority was a discard hierarchy: which technical details
must lose when reader comprehension and evidence depth compete. This layer therefore
keeps the same budgets and gates, but makes Decision comprehension, limitation fidelity
and one central mechanism outrank implementation-name inventory.

The canonical Reader Value layer creates no provider loop and no new request budget.
Fact/Evidence/Publication/Reader gates still rerun after repair and remain fail-closed.
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
ARTICLEは専門知識を見せる順番ではなく、読者が判断できる順番で書く。固定見出しや定型句は使わず、次の優先順位を他のReader/Style指示より上位の実行原則として扱う。

【実行優先順位】
1. Decision理解：冒頭3段落以内に①何が変わった ②それが読者の仕事・利用判断にどう関係する ③現時点の暫定判断（試す／比較する／待つ／見送る等）を置く。
2. 制約保持：重要な制約・対象範囲・例外・未検証条件は削らず、普通の日本語で1〜2文に圧縮してDecisionの近くに残す。制約を脚注扱いで最後へ追いやらない。
3. Evidence保持：Decisionを支える一次情報・重要数値・反証は残す。ただしEvidenceの深さを技術名の多さで表現しない。
4. 中核メカニズム：読者が「なぜそうなるか」を理解するための仕組みは原則1つを主役にする。2つ目以降は、それがないとDecisionか重要な制約を誤解する場合だけ本文へ入れる。
5. 実装名・略語・ベンチマーク名：Decisionも制約も変えない名前は本文から外すか、「複数の既存手法」「内部の圧縮方式」等の意味カテゴリへ圧縮する。一次情報に名前があることはARTICLEへ列挙する理由にならない。

・読者が前半で覚える中心メッセージは原則3つまで。①変化 ②判断 ③判断を変えうる重要な制約を優先する。
・冒頭約600文字では中核メカニズムを1つまでに絞り、Decisionに不要なAPI名・内部構造・精度名・ベンチマーク条件・実装識別子を並べない。名称より「何をする仕組みか」を先に書く。
・専門語を説明するために別の未説明専門語を持ち込まない。最初の専門語・略語は同じEvidenceの範囲で一度だけ普通の日本語に言い換える。新事実は足さない。
・問いかけや比喩は、それだけではReader Bridgeとみなさない。Human Appealは問いかけや比喩の数ではなく、「自分に関係する理由」「判断の速さ」「具体的な次Action」で作る。親しみのための前置きは増やさない。
・高密度な技術説明を2段落続けない。技術説明の次は新しい技術名を足さず、その事実が読者の判断・制約・行動のどれを変えるかへ戻る。
・方法名、略語、ベンチマーク、内部部品が3個以上並びそうなら、その列挙をEvidence inventoryとみなし本文から退避する。例外は、個々の名前の違い自体がDecisionを変える場合だけ。
・「面白さ」は架空の体験・感情・因果で作らない。Evidence内の意外な差分か判断の分かれ目を1つ選び、そこを記事の軸にする。
・本文後半でも新しい専門概念を次々追加しない。後半は前半のDecisionを、Evidence・条件・比較・次Actionで精密化する。
・タイトルは日本語として閉じた一文にし、引用符を対応させ、専門語だけのタイトルにしない。
""".strip()

READER_REPAIR_CONTRACT = r"""
【Reader Repair｜Factを固定した読者導線修正】
この修正では新しい調査・新しい事実追加をしない。前稿のFact/Evidenceを正本として、読者導線だけを修正する。
・Evidence URL、一次情報の意味、Decision/Score/Action、根拠付き数値・単位・固有名詞・条件を変えない。新しい数値、製品名、API名、比較対象、使用経験、感情、因果、保証表現を追加しない。
・修正の優先順位は Decision理解 → 重要な制約 → Evidence → 中核メカニズム1つ → 実装名の順。下位情報を残すために上位の理解を犠牲にしない。
・前稿の後半に既に存在するDecision/Actionは意味を変えずに冒頭3段落以内へ前倒ししてよい。問いかけ・比喩がDecision到達を遅らせている場合は削除または1文へ圧縮する。
・Reader Repair後の前半は、①何が変わった ②今どう判断する ③その判断を変えうる重要な制約、の3点を優先する。導入を長くしない。
・前稿にある重要な制約・対象範囲・例外・未検証条件は平易化のために削除してはいけない。意味を保った普通の日本語へ置換し、Decisionの直後または同じ判断段落に1〜2文で残す。
・冒頭約600文字では中核メカニズムを1つまでにする。Decisionに不要な専門語・実装識別子は後段へ移すのではなく、まず削除・カテゴリ化を検討する。
・方法名、略語、ベンチマーク、内部部品の列挙は、各名称がDecisionを変えない限り「複数の既存手法」等へ圧縮する。専門語を説明するための新しい専門語は禁止する。
・記事全体で新規概念を増やさず、既存Evidenceを「何を意味するか → なぜ判断に効くか → どんな制約があるか」の順へ並べ替える。Human Appealのための会話句・雑談・比喩は追加しない。
・Evidenceを落とさず、情報の置き場所と粒度を変えて読みやすくする。修正後も事実Gate、Evidence Gate、Publication Gate、Reader Gateをすべて再判定し、通らなければReadyにしない。
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
        if (
            os.getenv(FAST_LANE_ENV, "") == "1"
            and candidate_origin == "pending_retry"
            and evidence_result is not None
            and not getattr(pipeline_module, _SPENT_ATTR, False)
            and _reader_only_repairable(rows, _PENDING_REPAIRABLE)
        ):
            setattr(pipeline_module, _SPENT_ATTR, True)
            return True, "run208_reader_value_fast_lane_repair"

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
    pipeline_module.RUN345_READER_CONCEPT_HIERARCHY = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
