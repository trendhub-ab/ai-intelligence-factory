"""Run352 zero-API precision for Quality Retry and deterministic rescue.

Real Run38 artifact comparison showed two independent regressions after the original draft:

* the single Quality Retry repaired many Fact defects but rewrote reader-facing material that
  was outside the requested local repair, turning Curiosity/Reader Proximity from GOOD to REVIEW;
* the final deterministic rescue removed the substring ``圧倒的`` from ``だが圧倒的に`` and
  produced the malformed Japanese surface ``だがに``.

This overlay does not add a provider call, change retry count, relax any Fact/Evidence/
Publication gate, or manufacture replacement facts. It only (1) strengthens the instruction on
an already-authorized retry so non-target reader structure is preserved and no new unsupported
numbers/ROI/comparisons are introduced, and (2) removes a stranded adverbial particle when the
base subtractive rescue demonstrably created it by deleting one of its own hype tokens.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

_INSTALL_FLAG = "_run352_retry_preservation_installed"

RETRY_PRESERVATION_CONTRACT = """
【Run352 局所修正契約｜前回稿の読者価値を壊さない】
・これは全文リライトではありません。編集フィードバックで指摘された事実・数値・帰属・条件・対象節だけを直してください。
・指摘対象でない見出し、段落順、導入の読者接点、問い、比喩、具体例、筆者判断、結論の温度感は前回ARTICLEの表現を維持してください。
・claim / numbers / conditions の修正では、問題のある文だけを削除または根拠範囲へ弱め、周辺段落を新しい説明へ作り直さないでください。
・前回ARTICLEにない新しい数値、価格、速度、割合、ROI、コスト効果、競合比較、採用実績、固有名詞を修正の穴埋めとして追加しないでください。
・削除後に助詞だけが残る、文法が壊れる、読者への橋渡しが消える修正は禁止です。修正対象外の文章を短くして帳尻を合わせないでください。
""".strip()


def retry_feedback_with_preservation(quality_feedback: str, previous_article: str) -> str:
    """Add a strict local-edit contract only to an actual retry, never initial generation."""
    feedback = str(quality_feedback or "").strip()
    previous = str(previous_article or "").strip()
    if not feedback or not previous:
        return quality_feedback or ""
    if RETRY_PRESERVATION_CONTRACT in feedback:
        return feedback
    return feedback + "\n\n" + RETRY_PRESERVATION_CONTRACT


def _repair_stranded_adverb_particle(before: str, after: str) -> tuple[str, list[str]]:
    """Repair only particles stranded by the base rescue's exact hype-token deletion.

    The base rescue deletes ``圧倒的`` / ``劇的`` / ``革命的`` but not a following ``に``.
    We require an exact before-context containing ``<token>に`` and an exact after-context where
    the same local text survives with only the token missing. This cannot fire on unrelated ``に``.
    """
    original = str(before or "")
    repaired = str(after or "")
    changes: list[str] = []
    for token in ("圧倒的", "劇的", "革命的"):
        needle = token + "に"
        start = 0
        while True:
            idx = original.find(needle, start)
            if idx < 0:
                break
            prefix = original[max(0, idx - 18):idx]
            suffix = original[idx + len(needle):idx + len(needle) + 18]
            bad = prefix + "に" + suffix
            good = prefix + suffix
            if bad and bad in repaired:
                repaired = repaired.replace(bad, good, 1)
                changes.append(f"remove_stranded_ni_after_{token}")
            start = idx + len(needle)
    return repaired, changes


def repair_deterministic_rescue_surface(before: dict, rescued: dict) -> tuple[dict, list[str]]:
    """Repair proven grammar damage without restoring any unsupported claim."""
    out = dict(rescued or {})
    changes: list[str] = []
    for field in ("note_draft", "title_text", "action_text"):
        fixed, field_changes = _repair_stranded_adverb_particle(
            str((before or {}).get(field) or ""), str(out.get(field) or "")
        )
        if field_changes:
            out[field] = fixed
            changes.extend(f"{field}:{change}" for change in field_changes)
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


def install(pipeline_module: Any) -> Any:
    """Install the Run352 retry/rescue precision overlay idempotently."""
    p = pipeline_module
    if bool(getattr(p, _INSTALL_FLAG, False)):
        return p

    original_prompt = getattr(p, "build_decision_prompt", None)
    if callable(original_prompt):
        p.build_decision_prompt = _wrap_build_decision_prompt(original_prompt)

    original_rescue = getattr(p, "_apply_deterministic_publication_rescue", None)
    if callable(original_rescue):
        def rescue_with_surface_precision(parsed: dict, reason_rows):
            rescued, changes = original_rescue(parsed, reason_rows)
            fixed, grammar_changes = repair_deterministic_rescue_surface(parsed, rescued)
            merged_changes = list(changes or [])
            if grammar_changes:
                merged_changes.extend(grammar_changes)
            return fixed, list(dict.fromkeys(merged_changes))

        p._apply_deterministic_publication_rescue = rescue_with_surface_precision

    setattr(p, _INSTALL_FLAG, True)
    return p
