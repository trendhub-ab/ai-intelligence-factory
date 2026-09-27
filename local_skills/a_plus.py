"""A+ editorial orchestration for AIIF.

A+ keeps Gemini responsible for expressive prose while Local Skills owns the
pre-write article skeleton and the provider-free last-resort manuscript.

This module has no network or persistence side effects.
"""
from __future__ import annotations

from typing import Any, Mapping

from .compiler import compile_snapshot
from .production_canary import build_snapshot


PREWRITE_CONTRACT_ID = "a-plus-local-skeleton-v1"
LOCAL_FALLBACK_ID = "a-plus-local-fallback-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_prewrite_contract(
    evidence_result: Mapping[str, Any] | None = None,
    evidence_metadata: Mapping[str, Any] | None = None,
) -> str:
    """Return the deterministic Local Skills skeleton injected before Gemini writes.

    The contract does not invent article facts. It only fixes the order of reasoning
    and the relationship between MANAGEMENT DATA and the reader-facing article.
    """
    evidence_result = dict(evidence_result or {})
    evidence_metadata = dict(evidence_metadata or {})
    limitations = bool(evidence_result.get("limitations_disclosed"))
    freshness_limited = bool(evidence_result.get("freshness_scope_limited"))
    numeric_allowed = bool(evidence_result.get("numeric_claims_allowed", True))
    actor_allowed = bool(evidence_result.get("actor_attribution_allowed", True))
    qualifier_count = len(evidence_metadata.get("required_qualifiers") or [])

    guardrails = [
        "MANAGEMENT DATAのWhat / Why Important / Decision / Decision Reason / Actionを先に確定し、ARTICLEはその意味を変えずに読者向けへ展開する。",
        "ARTICLEの導入は一次情報で確認できる変化・意外性・読者の困りごとのいずれかから始め、一般論だけの前置きを置かない。",
        "本文は『何が変わったか → なぜ判断に関係するか → 必要な仕組み/条件 → 制約/反証 → 次のAction』を骨格にする。ただし見出し名や段落数は記事固有に変えてよい。",
        "専門用語は登場時に普通の日本語で役割を説明し、説明のためだけの専門語を増やさない。",
        "最終判断はDecisionと意味一致させ、Actionは『注視』だけへ潰さず、根拠範囲内の具体的な次の一手にする。",
        "Human Appealのために架空の体験談・感情・会話・新しい事実を足さない。面白さは事実の意外性、緊張、比較、判断の声から作る。",
    ]
    if limitations:
        guardrails.append("一次情報に残る制約・限界を、判断の直前または同じセクションで必ず見せる。")
    if freshness_limited:
        guardrails.append("時点が限定された事実は現在事実へ昇格させず、原資料公開時点の範囲を保つ。")
    if not numeric_allowed:
        guardrails.append("条件未確認の数値をARTICLEへ追加しない。")
    if not actor_allowed:
        guardrails.append("主体帰属が未確認の固有名詞を断定しない。")
    if qualifier_count:
        guardrails.append(f"Structured Evidenceのrequired_qualifiers（{qualifier_count}件）は削除せず自然な日本語へ展開する。")

    body = "\n".join(f"・{row}" for row in guardrails)
    return (
        f"[{PREWRITE_CONTRACT_ID}]\n"
        "Local Skillsが記事の骨格と必須要素を固定する。Geminiはこの骨格の中で"
        "人間らしいリズム、引力、比喩、言葉選びを担当する。\n"
        f"{body}\n"
        "このContractは追加Provider callを要求しない。"
    )


def _management_fields_complete(parsed: Mapping[str, Any]) -> bool:
    required_text = (
        "source_summary_text",
        "what_text",
        "why_important_text",
        "decision_text",
        "decision_reason_text",
        "action_text",
    )
    if not all(_text(parsed.get(key)) for key in required_text):
        return False
    try:
        int(parsed.get("score"))
    except (TypeError, ValueError):
        return False
    return True


def can_use_local_fallback(
    parsed: Mapping[str, Any] | None,
    reason_rows: list[dict] | None,
    evidence_result: Mapping[str, Any] | None,
) -> bool:
    """Allow provider-free fallback only after safe structured management data exists."""
    parsed = dict(parsed or {})
    if not _management_fields_complete(parsed):
        return False
    evidence_result = dict(evidence_result or {})
    state = _text(evidence_result.get("state")).upper()
    if state and state != "SUFFICIENT":
        return False
    if not bool(evidence_result.get("decision_scope_safe", True)):
        return False
    for row in reason_rows or []:
        if _text(row.get("gate")).lower() == "fact":
            return False
    return True


def compile_provider_free_fallback(
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source: str,
    primary_url: str,
    grounding: Mapping[str, Any] | None,
    evidence_context: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Render a complete Local Skills manuscript from already-established management data."""
    snapshot = build_snapshot(
        repo,
        parsed,
        source=source,
        primary_url=primary_url,
        grounding=grounding,
    )
    compiled = compile_snapshot(snapshot, evidence_context=evidence_context)
    out = dict(parsed)
    out.update(dict(compiled["parsed"]))

    # The final canonical manuscript builder owns the complete public footer.
    body, marker, _footer = str(out.get("note_draft") or "").rpartition("\n### Sources / Evidence")
    if marker:
        out["note_draft"] = body.rstrip() + "\n"

    meta = {
        "contract": LOCAL_FALLBACK_ID,
        "prewrite_contract": PREWRITE_CONTRACT_ID,
        "provider_article_surface_reused": False,
        "writer_blob_sha": compiled.get("writer_blob_sha"),
        "canonicalizer_blob_sha": compiled.get("canonicalizer_blob_sha"),
        "evidence_boundary_version": compiled.get("evidence_boundary_version"),
        "removed_unsupported_numeric_claims": int(
            (compiled.get("evidence_boundary") or {}).get("removed_count", 0)
        ),
    }
    out["_a_plus_local_fallback"] = dict(meta)
    return out, meta
