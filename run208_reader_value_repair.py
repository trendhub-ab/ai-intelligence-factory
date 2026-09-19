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
keeps the same gates, but makes Decision comprehension, limitation fidelity and necessary
mechanisms outrank implementation-name inventory. Numeric style quotas are superseded
by the current Editorial Blueprint in both first-pass and repair instructions.

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

from canonical_article_contract import canonical_reader_repair_contract, ensure_writer_contract

FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"
_INSTALLED_ATTR = "_run208_reader_value_repair_installed"
_SPENT_ATTR = "_run208_reader_value_repair_spent"
_BASE_RETRY_SPENT_ATTR = "_run360_base_quality_retry_spent"
_READER_REPAIR_SPENT_ATTR = "_run360_reader_repair_spent"
READER_VALUE_MARKER = "reader_value_review:"
_READER_ONLY_REPAIRABLE = (
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
# Pending Retry and fresh/article-revalidation share the same reader-only repair
# taxonomy. Pending remains cheaper because the fast lane still permits exactly one
# article and one reserved Reader Repair within its four provider-send ceiling.
_PENDING_REPAIRABLE = _READER_ONLY_REPAIRABLE
_FRESH_REPAIRABLE = _READER_ONLY_REPAIRABLE
_FRESH_EQUIVALENT_ORIGINS = frozenset({"new", "article_revalidation"})
_BASE_RETRY_OWNER_ORIGINS = _FRESH_EQUIVALENT_ORIGINS | frozenset({"pending_retry"})

READER_PATH_CONTRACT = r"""
【Reader Path Contract｜非エンジニアが迷子にならない順序】
ARTICLEは専門知識を見せる順番ではなく、読者が判断できる順番で書く。固定見出しや定型句は使わず、Editorial Blueprintと同じ読者判断基準で、次の優先順位を適用する。文章量・専門語・構成は個数ではなく理解に必要かで決める。

【実行優先順位】
1. Decision理解：冒頭で読者が迷わない位置に①何が変わった ②それが読者の仕事・利用判断にどう関係する ③現時点の暫定判断（試す／比較する／待つ／見送る等）を置く。
2. 制約保持：重要な制約・対象範囲・例外・未検証条件は削らず、意味を欠落させない普通の日本語でDecisionの近くに残す。制約を脚注扱いで最後へ追いやらない。
3. Evidence保持：Decisionを支える一次情報・重要数値・反証は残す。ただしEvidenceの深さを技術名の多さで表現しない。
4. 中核メカニズム：読者が「なぜそうなるか」を理解するための仕組みはCentral Conclusion / Capability Boundary / Reader Decisionの理解に必要な範囲で説明する。複数の仕組みや専門語の比較が必要なら残し、個数上限で削らない。
5. 実装名・略語・ベンチマーク名：Decisionも制約も変えない名前は本文から外すか、「複数の既存手法」「内部の圧縮方式」等の意味カテゴリへ圧縮する。一次情報に名前があることはARTICLEへ列挙する理由にならない。

・初稿の段階でReader Gateを後工程へ丸投げしない。専門名を残すか迷ったら、Decisionまたは重要制約を変える名前だけを残し、それ以外は削るか意味カテゴリへ圧縮する。
・読者が前半で必要とするメッセージはReader Questionと判断への関係で選ぶ。①変化 ②判断 ③判断を変えうる重要な制約を優先する。
・冒頭の説明は核心と判断の理解に必要な範囲にし、Decisionに不要なAPI名・内部構造・精度名・ベンチマーク条件・実装識別子を並べない。名称より「何をする仕組みか」を先に書く。
・専門語を説明するために別の未説明専門語を持ち込まない。最初の専門語・略語は同じEvidenceの範囲で一度だけ普通の日本語に言い換える。新事実は足さない。
・問いかけや比喩は、それだけではReader Bridgeとみなさない。Human Appealは問いかけや比喩の数ではなく、「自分に関係する理由」「判断の速さ」「具体的な次Action」で作る。親しみのための前置きは増やさない。
・技術説明と読者の判断・制約・行動との関係が見えなくなった箇所は、既存Evidenceの意味へ戻す。段落数で機械的に説明を打ち切らない。
・方法名、略語、ベンチマーク、内部部品の列挙は、個々の違いが核心・制約・Decisionに必要かを確認する。不要なEvidence inventoryは削除または意味カテゴリへ統合し、必要な名前は個数にかかわらず残す。
・「面白さ」は架空の体験・感情・因果で作らない。Evidence内の意外な差分か判断の分かれ目を1つ選び、そこを記事の軸にする。
・本文後半でも新しい専門概念を次々追加しない。後半は前半のDecisionを、Evidence・条件・比較・次Actionで精密化する。
・タイトルは日本語として閉じた一文にし、引用符を対応させ、専門語だけのタイトルにしない。
""".strip()

READER_REPAIR_CONTRACT = canonical_reader_repair_contract()

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


def is_reader_only_repair(rows: list[dict], hard_severity: str = "HARD") -> bool:
    """Shared instruction classification; this does not authorize or spend a retry."""
    return _reader_only_repairable(rows, _FRESH_REPAIRABLE, hard_severity)


def _is_decision_voice_row(pipeline_module: Any, row: dict) -> bool:
    """Allow only the audited Human Appeal decision-voice repair to travel with Reader repair."""
    message = _message(row)
    code = str((row or {}).get("reason_code") or "")
    expected = str(getattr(
        pipeline_module,
        "REASON_CODE_APPEAL_DECISION_VOICE_LOSS",
        "APPEAL_DECISION_VOICE_LOSS",
    ))
    return (
        code == expected
        or message in {"decision_voice_missing", "human_appeal_materially_degraded_after_reedit"}
    )


def _dedicated_reader_repairable(
    pipeline_module: Any,
    rows: list[dict],
    labels: tuple[str, ...],
    hard_severity: str | None = None,
) -> bool:
    """Classify the bounded Reader owner without turning arbitrary REVIEW debt into Reader work.

    A real 2026-09-19 article_validation exposed an owner-ordering gap: after the one HARD
    Fact retry, the remaining bundle contained Reader accessibility defects plus
    decision_voice_missing. Both are repaired from the same fixed Evidence/Decision surface,
    but the historical every-row-must-be-reader rule prevented the dedicated Reader owner
    from claiming its already-budgeted second slot.

    At least one canonical Reader row is still required. The only non-Reader companion allowed
    is the audited Decision Voice loss. HARD rows and every other REVIEW class remain ineligible.
    """
    if not rows:
        return False
    has_reader = False
    for row in rows:
        if hard_severity and str((row or {}).get("severity") or "") == hard_severity:
            return False
        message = _message(row)
        if READER_VALUE_MARKER in message:
            if not any(label in message for label in labels):
                return False
            has_reader = True
            continue
        if _is_decision_voice_row(pipeline_module, row):
            continue
        return False
    return has_reader


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
            "専門名・略語は個数にかかわらず、個々の名称の違いが核心・重要制約・Decisionの理解に必要かを確認し、不要なものだけ意味カテゴリへ統合する。"
            "これは『説明を追加する』作業ではなく『不要な名称を捨てる』作業である。"
        )
        directives.append(
            "【実行必須：専門語の連鎖を切る】専門語を別の専門語で説明しない。必要な専門概念は普通の日本語で役割を示し、関係が伝わらない箇所で、"
            "読者の判断・制約・Actionのどれが変わるかを書く。段落数による強制切替や説明文の水増しはしない。"
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

    if "decision_voice_missing" in messages or "human_appeal_materially_degraded_after_reedit" in messages:
        directives.append(
            "【実行必須：Decision Voiceを復元する】MANAGEMENT DATAの既存Decision / Decision Score / Decision Reason / Actionと、"
            "前稿に残る一次Evidenceだけを使い、編集者自身の判断を自然な日本語で1箇所に戻す。"
            "『私なら小さく試す／比較する／待つ／見送る』等の距離感は既存Decisionと一致させる。"
            "新しいFact、利用経験、感情、因果、保証、緊急度を作らず、Reader導線の修正と同じ1回で完了する。"
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
    # one reader-only repair for fresh/article-revalidation and the bounded Pending fast lane.
    pipeline_module.MAX_QUALITY_RETRIES = max(2, int(getattr(pipeline_module, "MAX_QUALITY_RETRIES", 1) or 1))

    def should_attempt_dynamic_retry_with_reader_repair(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        rows = list(reason_rows or [])
        allowed, reason = original_retry(rows, evidence_result, candidate_origin)

        if allowed:
            if candidate_origin in _BASE_RETRY_OWNER_ORIGINS:
                if bool(getattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, False)):
                    # The live base policy returns allowed=True for repairable REVIEW rows.
                    # Evaluate the already-budgeted Reader owner before returning base-spent.
                    if (
                        candidate_origin in _FRESH_EQUIVALENT_ORIGINS
                        and _fresh_evidence_safe(pipeline_module, evidence_result)
                    ):
                        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
                        if _dedicated_reader_repairable(
                            pipeline_module, rows, _FRESH_REPAIRABLE, hard
                        ):
                            if bool(getattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, False)):
                                return False, "run360_reader_repair_already_spent"
                            setattr(pipeline_module, _READER_REPAIR_SPENT_ATTR, True)
                            return True, "run341_production_reader_repair"
                    return False, "run360_base_quality_retry_already_spent"
                setattr(pipeline_module, _BASE_RETRY_SPENT_ATTR, True)
            return allowed, reason

        if reason != "reader_value_review_no_retry":
            return allowed, reason

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
        return ensure_writer_contract(prompt)

    def build_dynamic_retry_instruction_with_reader_repair(reason_rows: list[dict]):
        rows = list(reason_rows or [])
        instruction, sections = original_retry_instruction(rows)
        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
        reader_only = _dedicated_reader_repairable(
            pipeline_module, rows, _FRESH_REPAIRABLE, hard
        )
        if reader_only:
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
