"""Run284/352/360/370/371/373/375: bounded Reader recovery policy."""
from __future__ import annotations

import inspect
import re
from typing import Any, Callable

_INSTALL_FLAG = "_run284_reader_recovery_precision_installed"
_RUN352_FLAG = "_run352_retry_preservation_installed"
_SPENT_FLAG = "_run284_current_policy_reader_repair_spent"
READER_VALUE_MARKER = "reader_value_review:"
_DANGEROUS_POLISH_PATTERN = r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"
_READER_REPAIR_FEEDBACK_MARKERS = (
    "【Reader Repair｜Factを固定した読者導線修正】",
    "【RUN359 Reader Repair Execution Contract】",
)
_READER_REPAIR_ALLOWED_ORIGINS = frozenset({"current_policy_ready_recovery", "pending_retry_validation"})
_REPAIRABLE_READER_LABELS = (
    "dense_report_cluster", "repetitive_insight", "multi_axis_reader_weakness",
    "non_engineer_access_failure", "final_surface_multi_axis_reader_weakness",
    "final_surface_non_engineer_access_failure", "final_surface_summary_jargon_cluster",
    "final_surface_summary_fragment",
)

RETRY_PRESERVATION_CONTRACT = """
【Run352 局所修正契約｜前回稿の読者価値を壊さない】
・これは全文リライトではありません。編集フィードバックで指摘された事実・数値・帰属・条件・対象節だけを直してください。
・指摘対象でない見出し、段落順、導入の読者接点、問い、比喩、具体例、筆者判断、結論の温度感は前回ARTICLEの表現を維持してください。
・claim / numbers / conditions の修正では、問題のある文だけを削除または根拠範囲へ弱め、周辺段落を新しい説明へ作り直さないでください。
・前回ARTICLEにない新しい数値、価格、速度、割合、ROI、コスト効果、競合比較、採用実績、固有名詞を修正の穴埋めとして追加しないでください。
・削除後に助詞だけが残る、文法が壊れる、読者への橋渡しが消える修正は禁止です。修正対象外の文章を短くして帳尻を合わせないでください。
""".strip()

RUN373_READER_REPAIR_BASE_CONTRACT = """
【RUN373 Reader Pull Contract｜既存Factだけで読みやすくする】
・Fact / Evidence / Decision / 重要な制約は固定する。Gate閾値は変更しない。
・前回ARTICLEにない事実、数値、経験談、人物、用途、比較、効果を追加しない。
・新しい具体例や数値比喩を捏造しない。一方、既存Factの順序変更、短文化、平易な言い換え、文の長短、問いかけではない読者向けの直接表現、既存Fact同士の対比は許可する。
・Human Appealを上げるための雑談や架空体験は足さない。ただし、文章のリズムや『自分の判断に何が関係するか』という読者接点まで禁止してはいけない。
・専門語を削るためにEvidenceやDecision条件を落とさない。固有名詞が判断を変える場合は保持する。
""".strip()

RUN373_READER_REPAIR_RULES = {
    "dense_report_cluster": "報告書調の列挙を削る。同一段落の判断に不要な実装名・方式名・補足を統合し、1段落1論点にする。Evidence・重要制約は削らない。",
    "multi_axis_reader_weakness": "冒頭3段落を『何が変わった→今どう判断する→判断を変える重要制約』の順にする。既存Factの対比と平易な読者向け表現で流れを作るが、新しい比喩や事実は足さない。",
    "non_engineer_access_failure": "専門語を別の専門語で説明しない。Decisionを変えない専門名・略語は普通名詞へカテゴリ化し、冒頭約600文字の中核専門概念を1つまでにする。",
    "repetitive_insight": "同じ判断・効用・注意点の言い換えを1回に統合する。Evidenceや反証を重複と誤認して削除しない。",
    "final_surface_summary_jargon_cluster": "『何が出た？』等の要約面では製品名以外の専門語列挙を避け、読者が得る変化を普通の日本語1文で完結させる。",
    "final_surface_summary_fragment": "『何が出た？』『結論は？』等の要約面を、主語と述語を持つ独立した自然な日本語1文にする。断片句・名詞止め・途中で切れた文を残さず、新しい事実は足さない。",
    "final_surface_multi_axis_reader_weakness": "最終要約を、変化・判断・制約が各1文で分かる形へ圧縮する。",
    "final_surface_non_engineer_access_failure": "最終要約の略語・内部部品名を削り、非エンジニアが単独で意味を取れる文にする。",
}


def _reader_label(message: str) -> str:
    """Extract one exact Reader reason label; never match labels as substrings."""
    text = str(message or "")
    if READER_VALUE_MARKER not in text:
        return ""
    tail = text.split(READER_VALUE_MARKER, 1)[1].lstrip()
    match = re.match(r"([a-z0-9_]+)", tail)
    return str(match.group(1) if match else "")


def deterministic_reader_repair_plan(reason_rows: list[dict]) -> tuple[str, ...]:
    """Translate exact observed Reader labels into a stable, zero-API edit plan."""
    labels: list[str] = []
    for row in reason_rows or []:
        label = _reader_label(str((row or {}).get("message") or (row or {}).get("reason") or ""))
        if label in _REPAIRABLE_READER_LABELS and label not in labels:
            labels.append(label)
    return tuple(labels)


def reader_repair_feedback(reason_rows: list[dict]) -> str:
    labels = deterministic_reader_repair_plan(reason_rows)
    if not labels:
        return ""
    rules = [RUN373_READER_REPAIR_RULES[label] for label in labels]
    return (
        RUN373_READER_REPAIR_BASE_CONTRACT
        + "\n\n【RUN373 Reason-Specific Reader Repair｜0-API決定論プラン】\n"
        + "\n".join(f"・{rule}" for rule in rules)
    )


def disable_overbroad_japanese_polish(pipeline_module: Any) -> int:
    fixes = tuple(getattr(pipeline_module, "_JAPANESE_SAFE_FIXES", ()) or ())
    filtered = tuple((p, r) for p, r in fixes if str(getattr(p, "pattern", "")) != _DANGEROUS_POLISH_PATTERN)
    pipeline_module._JAPANESE_SAFE_FIXES = filtered
    return len(fixes) - len(filtered)


def _message(row: dict) -> str:
    return str((row or {}).get("message") or (row or {}).get("reason") or "")


def _reader_only_repairable(rows: list[dict], hard_severity: str) -> bool:
    if not rows:
        return False
    saw = False
    for row in rows:
        if str((row or {}).get("severity") or "") == hard_severity:
            return False
        label = _reader_label(_message(row))
        if label not in _REPAIRABLE_READER_LABELS:
            return False
        saw = True
    return saw


def _evidence_is_safe_for_reader_repair(pipeline_module: Any, evidence_result: dict | None) -> bool:
    if not isinstance(evidence_result, dict):
        return False
    sufficient = str(getattr(pipeline_module, "EVIDENCE_SUFFICIENT", "SUFFICIENT"))
    return str(evidence_result.get("state") or "") == sufficient and evidence_result.get("decision_scope_safe") is True


def retry_feedback_with_preservation(quality_feedback: str, previous_article: str) -> str:
    feedback, previous = str(quality_feedback or "").strip(), str(previous_article or "").strip()
    if not feedback or not previous:
        return quality_feedback or ""
    if any(marker in feedback for marker in _READER_REPAIR_FEEDBACK_MARKERS):
        rows = [{"message": line} for line in feedback.splitlines() if READER_VALUE_MARKER in line]
        plan = reader_repair_feedback(rows)
        return feedback if not plan or plan in feedback else feedback + "\n\n" + plan
    if RETRY_PRESERVATION_CONTRACT in feedback:
        return feedback
    return feedback + "\n\n" + RETRY_PRESERVATION_CONTRACT


def _repair_stranded_adverb_particle(before: str, after: str) -> tuple[str, list[str]]:
    original, repaired, changes = str(before or ""), str(after or ""), []
    for token in ("圧倒的", "劇的", "革命的"):
        needle, start = token + "に", 0
        while True:
            idx = original.find(needle, start)
            if idx < 0:
                break
            prefix, suffix = original[max(0, idx-18):idx], original[idx+len(needle):idx+len(needle)+18]
            bad, good = prefix + "に" + suffix, prefix + suffix
            if bad and bad in repaired:
                repaired = repaired.replace(bad, good, 1)
                changes.append(f"remove_stranded_ni_after_{token}")
            start = idx + len(needle)
    return repaired, changes


def repair_deterministic_rescue_surface(before: dict, rescued: dict) -> tuple[dict, list[str]]:
    out, changes = dict(rescued or {}), []
    for field in ("note_draft", "title_text", "action_text"):
        fixed, field_changes = _repair_stranded_adverb_particle(str((before or {}).get(field) or ""), str(out.get(field) or ""))
        if field_changes:
            out[field] = fixed
            changes.extend(f"{field}:{c}" for c in field_changes)
    return out, changes


def _wrap_build_decision_prompt(original: Callable[..., Any]) -> Callable[..., Any]:
    signature = inspect.signature(original)

    def wrapped(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        feedback = str(bound.arguments.get("quality_feedback") or "")
        previous = str(bound.arguments.get("previous_article") or "")
        if feedback and previous:
            bound.arguments["quality_feedback"] = retry_feedback_with_preservation(feedback, previous)
        return original(*bound.args, **bound.kwargs)

    wrapped.__name__ = getattr(original, "__name__", "build_decision_prompt")
    wrapped.__doc__ = getattr(original, "__doc__", None)
    return wrapped


def _install_run352_precision(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _RUN352_FLAG, False)):
        return pipeline_module
    original_prompt = getattr(pipeline_module, "build_decision_prompt", None)
    if callable(original_prompt):
        pipeline_module.build_decision_prompt = _wrap_build_decision_prompt(original_prompt)
    original_rescue = getattr(pipeline_module, "_apply_deterministic_publication_rescue", None)
    if callable(original_rescue):
        def rescue_with_surface_precision(parsed: dict, reason_rows):
            rescued, changes = original_rescue(parsed, reason_rows)
            fixed, grammar_changes = repair_deterministic_rescue_surface(parsed, rescued)
            return fixed, list(dict.fromkeys(list(changes or []) + grammar_changes))
        pipeline_module._apply_deterministic_publication_rescue = rescue_with_surface_precision
    setattr(pipeline_module, _RUN352_FLAG, True)
    return pipeline_module


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        _install_run352_precision(pipeline_module)
        return pipeline_module
    disable_overbroad_japanese_polish(pipeline_module)
    original_retry_policy = pipeline_module.should_attempt_dynamic_retry
    setattr(pipeline_module, _SPENT_FLAG, False)

    def wrapped_retry(reason_rows, evidence_result, candidate_origin="new"):
        allowed, reason = original_retry_policy(reason_rows, evidence_result, candidate_origin)
        if allowed:
            return allowed, reason
        if candidate_origin not in _READER_REPAIR_ALLOWED_ORIGINS or reason != "reader_value_review_no_retry":
            return allowed, reason
        if bool(getattr(pipeline_module, _SPENT_FLAG, False)) or not _evidence_is_safe_for_reader_repair(pipeline_module, evidence_result):
            return allowed, reason
        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
        if not _reader_only_repairable(list(reason_rows or []), hard):
            return allowed, reason
        setattr(pipeline_module, _SPENT_FLAG, True)
        lane = "pending_retry" if candidate_origin == "pending_retry_validation" else "current_policy"
        return True, f"run284_{lane}_reader_repair"

    pipeline_module.should_attempt_dynamic_retry = wrapped_retry
    _install_run352_precision(pipeline_module)
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
