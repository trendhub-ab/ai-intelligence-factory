"""A+ editorial orchestration for AIIF.

A+ keeps Gemini responsible for expressive prose while Local Skills owns the
pre-write article skeleton and the provider-free last-resort manuscript.

This module has no network or persistence side effects.
"""
from __future__ import annotations

from typing import Any, Mapping

from .compiler import compile_snapshot
from .production_canary import build_snapshot


PREWRITE_CONTRACT_ID = "a-plus-local-skeleton-v2"
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
        "Decisionコードを『導入する／導入しない』へ固定変換しない。導入・採用・本番移行という語は、読者が実際に採用できる製品・機能・仕組みが対象で、Actionも採用や試用を扱う場合だけ使う。歴史・設立・判決・事件・制度・研究・ベンチマーク等では、確認・比較・検証・評価・追跡・基準点にする等、その記事固有のActionに合わせる。",
        "上の語彙制約は結論だけでなく、Why Important・タイトル・リード・本文・見出しにも適用する。対象が『導入するもの』ではないのに、実務性を出すためだけに導入・採用・PoC・本番移行・技術選定へ話を曲げない。",
        "歴史・設立・宣言を扱う記事では、一次情報から確認できる『当時何を掲げたか／何を約束したか／どこが不確実だったか』を中心にし、後年との比較は別の一次情報がある場合だけ事実として書く。比較根拠がない場合は『後年の公式発表と比較する基準点にする』というActionに留める。",
        "非専門読者に不要な人名・肩書き・略語の列挙を減らす。CTO、LLM、API等を残す必要がある場合は、初出で役割が普通の日本語で分かるようにする。",
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


def repair_unbalanced_japanese_quotes(value: Any) -> str:
    """Remove only unmatched Japanese quote marks; never rewrite title words."""
    text = _text(value)
    if not text:
        return ""
    chars = list(text)
    remove: set[int] = set()
    for opener, closer in (("「", "」"), ("『", "』")):
        stack: list[int] = []
        for index, char in enumerate(chars):
            if index in remove:
                continue
            if char == opener:
                stack.append(index)
            elif char == closer:
                if stack:
                    stack.pop()
                else:
                    remove.add(index)
        remove.update(stack)
    if not remove:
        return text
    return "".join(char for index, char in enumerate(chars) if index not in remove).strip()


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
        gate = _text(row.get("gate")).lower()
        code = _text(row.get("reason_code")).upper()
        if gate == "fact":
            return False
        if any(token in code for token in ("FACT_", "EVIDENCE_", "SOURCE_", "GROUNDING")):
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


def render_provider_compatible_fallback(
    pipeline_module,
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source_info: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Compile Local Skills and serialize it into the existing provider response contract."""
    source = _text(repo.get("source")) or "Unknown"
    primary_url = _text(source_info.get("primary_url")) or _text(repo.get("url"))
    evidence_urls = []
    for value in list(source_info.get("evidence_urls") or []):
        url = _text(value)
        if url and url not in evidence_urls:
            evidence_urls.append(url)
    if primary_url and primary_url not in evidence_urls:
        evidence_urls.append(primary_url)
    grounding = {
        "grounding_status": _text(source_info.get("method")) or "Source Native",
        "evidence_urls": evidence_urls,
    }
    evidence_context = _text(source_info.get("verification_context")) or _text(source_info.get("context"))
    fallback, meta = compile_provider_free_fallback(
        repo,
        parsed,
        source=source,
        primary_url=primary_url,
        grounding=grounding,
        evidence_context=evidence_context,
    )

    score = int(fallback.get("score") or parsed.get("score") or 0)
    breakdown = _text(parsed.get("score_breakdown_text"))
    if not breakdown:
        breakdown = (
            f"Business Impact 0/25; Technical Impact 0/25; Urgency 0/20; "
            f"Market Impact 0/15; Reliability 0/15; 合計 {score}/100"
        )
    article_value = int(parsed.get("article_value") or score)
    token = _text(getattr(pipeline_module, "SECTION_SPLIT_TOKEN", "=== ARTICLE ==="))
    response_text = "\n".join([
        "=== MANAGEMENT DATA ===",
        f"・Source Summary: {_text(fallback.get('source_summary_text'))}",
        f"・What: {_text(fallback.get('what_text'))}",
        f"・Why Important: {_text(fallback.get('why_important_text'))}",
        f"・Decision: {_text(fallback.get('decision_text')).upper()}",
        f"・Decision Reason: {_text(fallback.get('decision_reason_text'))}",
        f"・Decision Score: {breakdown}",
        f"・Action: {_text(fallback.get('action_text'))}",
        f"・Article Value: {max(0, min(100, article_value))}",
        "",
        token,
        _text(fallback.get("title_text")),
        "",
        str(fallback.get("note_draft") or "").strip(),
    ]).strip() + "\n"
    return response_text, meta
