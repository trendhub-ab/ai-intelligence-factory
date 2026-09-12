"""Run208/341/342/344/345/354/359/360: bounded Reader Value repair and first-pass Reader Path.

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
keeps the same gates, but makes Decision comprehension, limitation fidelity and one
central mechanism outrank implementation-name inventory.

Run354 keeps article_validation semantically aligned with fresh Production for Reader-only
retry authorization. article_validation remains read-only because persistence is controlled by
its caller; only the quality/retry policy matches the new-candidate path when Evidence is safe.

Run359 is based on the 2026-09-12 RubyGems Production specimen: a quality repair could
preserve the same jargon inventory and then fail Reader/final-summary review again. The
repair prompt translates concrete gate reasons into executable deletion/category-compression
operations while preserving inherited safety rules.

Run360 is based on ONE-SHOT Run47. Three generated manuscripts reached Ready=0 because
Fact/Publication repair and Reader restructuring were mixed in the same retry, while a later
preservation layer simultaneously told the model to keep paragraph order. A manuscript that
used its one generic quality retry could then retain a reader-only blocker with no dedicated
repair opportunity. Run360 makes the two repair owners orthogonal:
- at most one ordinary Fact/Quality retry per candidate;
- Reader Repair instructions are added only when every blocking row is reader-only;
- after re-gating, at most one dedicated Reader Repair may run when Evidence is SUFFICIENT
  and decision_scope_safe is true;
- the per-candidate budget resets on a fresh first-pass prompt;
- no thresholds are relaxed and no retry loop is introduced beyond these two bounded owners.

Fact/Evidence/Publication/Reader gates always rerun and remain fail-closed.
"""
from __future__ import annotations

import os
from typing import Any

FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"
_INSTALLED_ATTR = "_run208_reader_value_repair_installed"
_SPENT_ATTR = "_run208_reader_value_repair_spent"
_BASE_RETRY_SPENT_ATTR = "_run360_base_quality_retry_spent"
_READER_REPAIR_SPENT_ATTR = "_run360_reader_repair_spent"
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
_FRESH_EQUIVALENT_ORIGINS = frozenset({"new", "article_revalidation"})

READER_PATH_CONTRACT = r"""
【Reader Path Contract｜非エンジニアが迷子にならない順序】
ARTICLEは専門知識を見せる順番ではなく、読者が判断できる順番で書く。固定見出しや定型句は使わず、次の優先順位を他のReader/Style指示より上位の実行原則として扱う。

【実行優先順位】
1. Decision理解：冒頭3段落以内に①何が変わった ②それが読者の仕事・利用判断にどう関係する ③現時点の暫定判断（試す／比較する／待つ／見送る等）を置く。
2. 制約保持：重要な制約・対象範囲・例外・未検証条件は削らず、普通の日本語で1〜2文に圧縮してDecisionの近くに残す。制約を脚注扱いで最後へ追いやらない。
3. Evidence保持：Decisionを支える一次情報・重要数値・反証は残す。ただしEvidenceの深さを技術名の多さで表現しない。
4. 中核メカニズム：読者が「なぜそうなるか」を理解するための仕組みは原則1つを主役にする。2つ目以降は、それがないとDecisionか重要な制約を誤解する場合だけ本文へ入れる。
5. 実装名・略語・ベンチマーク名：Decisionも制約も変えない名前は本文から外すか、「複数の既存手法」「内部の圧縮方式」等の意味カテゴリへ圧縮する。一次情報に名前があることはARTICLEへ列挙する理由にならない。

・初稿の段階でReader Gateを後工程へ丸投げしない。専門名を残すか迷ったら、Decisionまたは重要制約を変える名前だけを残し、それ以外は削るか意味カテゴリへ圧縮する。
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

_READER_DENSITY_LABELS = (
    "dense_report_cluster", "multi_axis_reader_weakness", "non_engineer_access_failure",
    "final_surface_multi_axis_reader_weakness", "final_surface_non_engineer_access_failure",
)


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


def _run359_targeted_repair(rows: list[dict]) -> str:
    """Turn actual Reader failures into observable edit operations, zero API by itself."""
    messages = "\n".join(_message(row) for row in rows or [])
    directives: list[str] = []

    if any(label in messages for label in _READER_DENSITY_LABELS):
        directives.append(
            "【実行必須：専門語密度を下げる】前稿を段落ごとに見直し、Decision・重要制約・一次Evidenceの意味を変えない専門名、略語、内部部品名、方式名は削除する。"
            "同じ段落に専門名・略語が3個以上残る場合、個々の名称の違いがDecisionを変える根拠を本文中で示せないものは意味カテゴリへ統合する。"
            "これは『説明を追加する』作業ではなく『不要な名称を捨てる』作業である。"
        )
        directives.append(
            "【実行必須：専門語の連鎖を切る】専門語を別の専門語で説明しない。最初に必要な専門概念は普通の日本語1文で意味を置き、その直後は新しい技術名ではなく、"
            "読者の判断・制約・Actionのどれが変わるかを書く。高密度な技術段落を連続させない。"
        )

    if "final_surface_summary_jargon_cluster" in messages:
        directives.append(
            "【実行必須：30秒要約の素材を平易化する】最終要約は本文から自動抽出されるため、source_summary/冒頭/why/conclusion/final/actionの候補文そのものを平易にする。"
            "要約候補文では固有の実装名や略語の列挙を避け、『何が変わった』『なぜ読者に関係する』『何をする』が専門知識なしで一読できる文にする。"
            "Factを削るのではなく、Decisionに不要な名称を削る。"
        )

    if "repetitive_insight" in messages:
        directives.append(
            "【実行必須：重複を削る】同じ核心説明を複数箇所に残さず1箇所へ統合し、後段はその事実が判断に与える意味へ進める。"
        )

    if "final_surface_summary_fragment" in messages:
        directives.append(
            "【実行必須：要約候補文を完結させる】冒頭・why・conclusion・final/actionの候補文を読点で切れた断片にせず、短い完結文にする。"
        )

    if not directives:
        return ""
    return "\n".join(["【RUN359 Reader Repair Execution Contract】", *directives])


def install(pipeline_module: Any) -> Any:
    """Install canonical Reader Value policy idempotently."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_retry = pipeline_module.should_attempt_dynamic_retry
    original_prompt = pipeline_module.build_decision_prompt
    original_retry_instruction = pipeline_module.build_dynamic_retry_instruction
    setattr(pipeline_module, _SPENT_ATTR, False)
    setattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, False)
    setattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, False)

    # The base pipeline loop is bounded by MAX_QUALITY_RETRIES. Run360 raises only the loop
    # ceiling; the owner-specific state below still allows at most one ordinary retry plus
    # one reader-only repair for a fresh/article-revalidation candidate.
    pipeline_module.MAX_QUALITY_RETRIES = max(2, int(getattr(pipeline_module, "MAX_QUALITY_RETRIES", 1) or 1))

    def should_attempt_dynamic_retry_with_reader_repair(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        allowed, reason = original_retry(reason_rows, evidence_result, candidate_origin)

        if allowed:
            if candidate_origin in _FRESH_EQUIVALENT_ORIGINS:
                if bool(getattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, False)):
                    return False, "run360_base_quality_retry_already_spent"
                setattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, True)
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

        if candidate_origin in _FRESH_EQUIVALENT_ORIGINS and _fresh_evidence_safe(pipeline_module, evidence_result):
            hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
            if _reader_only_repairable(rows, _FRESH_REPAIRABLE, hard):
                if bool(getattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, False)):
                    return False, "run360_reader_repair_already_spent"
                setattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, True)
                return True, "run341_production_reader_repair"

        return allowed, reason

    def build_decision_prompt_with_reader_path(*args: Any, **kwargs: Any) -> str:
        quality_feedback = str(args[4] if len(args) > 4 else kwargs.get("quality_feedback") or "")
        previous_article = str(kwargs.get("previous_article") or "")
        if not quality_feedback.strip() and not previous_article.strip():
            # Fresh candidate boundary. Retry ownership must never leak into the next article.
            setattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, False)
            setattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, False)
        prompt = str(original_prompt(*args, **kwargs) or "")
        return prompt.rstrip() + "\n\n" + READER_PATH_CONTRACT + "\n"

    def build_dynamic_retry_instruction_with_reader_repair(reason_rows: list[dict]):
        rows = list(reason_rows or [])
        instruction, sections = original_retry_instruction(rows)
        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
        reader_only = _reader_only_repairable(rows, _FRESH_REPAIRABLE, hard)
        if reader_only:
            # Run367: Run171's local Fact-retry guidance is inherited by this
            # wrapper. Its global restructuring ban contradicts Reader Repair's
            # explicit permission to reorder existing facts. Remove only that
            # prohibition; keep the ban on new facts and every acceptance gate.
            instruction = str(instruction).replace(
                "記事全体の再構成や新事実の追加はしないでください。",
                "新事実の追加はしないでください。",
            )
            instruction = str(instruction).rstrip() + "\n\n" + READER_REPAIR_CONTRACT
            targeted = _run359_targeted_repair(rows)
            if targeted:
                instruction = instruction.rstrip() + "\n\n" + targeted
        return instruction, sections

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_reader_repair
    pipeline_module.build_decision_prompt = build_decision_prompt_with_reader_path
    pipeline_module.build_dynamic_retry_instruction = build_dynamic_retry_instruction_with_reader_repair
    pipeline_module.RUN341_PRODUCTION_READER_REPAIR = True
    pipeline_module.RUN342_READER_DECISION_DISTANCE = True
    pipeline_module.RUN344_READER_LIMITATION_BRIDGE = True
    pipeline_module.RUN345_READER_CONCEPT_HIERARCHY = True
    pipeline_module.RUN354_VALIDATION_RETRY_PARITY = True
    pipeline_module.RUN359_READER_REPAIR_EXECUTION = True
    pipeline_module.RUN360_RETRY_OWNER_ORTHOGONALITY = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
