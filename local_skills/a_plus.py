"""A+ editorial orchestration for AIIF.

A+ keeps Gemini responsible for expressive prose while Local Skills owns the
pre-write article skeleton and the provider-free last-resort manuscript.

This module has no network or persistence side effects.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping

from .compiler import compile_snapshot
from .production_canary import build_snapshot


PREWRITE_CONTRACT_ID = "a-plus-local-skeleton-v2"
LOCAL_FALLBACK_ID = "a-plus-local-fallback-v1"

_META_SUMMARY_PHRASES = ("つまり", "要するに", "重要なのは", "ポイントは", "結局")
_SPEAKER_PHRASES = ("私なら", "私であれば")
_ABSTRACT_CLOSING_TERMS = ("重要", "判断", "選択肢", "岐路", "競争力", "未来", "本質", "鍵")
_NATURALNESS_REPAIR_GUIDANCE = {
    "section_structure_repetition": (
        "同じ『説明→意味→結論』の型を節ごとに繰り返さない。対象節の一部はEvidenceから始め、"
        "別の節は事実だけで止めるなど、情報を落とさず運びを変える。"
    ),
    "uniform_conclusion_cadence": (
        "各節を同じ強さの結論で閉じない。必要な強い判断だけ残し、重複するメタ要約や結論は"
        "文脈へ吸収する。"
    ),
    "speaker_voice_position_repetition": (
        "『私なら』等の話者判断を毎回同じ位置に置かない。Evidenceから判断が十分伝わる節では"
        "話者を前に出さず、具体的な条件・選択肢をそのまま置く。"
    ),
    "abstract_closing_cluster": (
        "抽象語だけの締めを重ねない。記事固有のEvidence・条件・Actionで閉じられる箇所は"
        "具体側へ戻す。"
    ),
}


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


def _naturalness_v2_sections(text: str) -> list[dict[str, Any]]:
    body = text or ""
    matches = list(re.finditer(r"^#{2,3}\s+(.+)$", body, re.MULTILINE))
    result: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_body = body[match.end():end].strip()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?])\s*", section_body)
            if sentence.strip()
        ]
        result.append(
            {
                "index": index + 1,
                "heading": match.group(1).strip(),
                "body": section_body,
                "sentences": sentences,
            }
        )
    return result


def _naturalness_v2_speaker_position(sentences: list[str]) -> str:
    for index, sentence in enumerate(sentences):
        if not any(phrase in sentence for phrase in _SPEAKER_PHRASES):
            continue
        if index == len(sentences) - 1:
            return "final"
        if index >= max(0, len(sentences) - 2):
            return "late"
        return "early"
    return "none"


def editorial_naturalness_v2_diagnostics(text: str) -> dict[str, Any]:
    """Describe structural AI-like repetition without gaining Ready authority.

    P2 signals may refine an already-authorized quality retry. P3 is advisory.
    This detector never creates a Fact/Evidence/Publications gate and can never
    block Ready on its own.
    """
    sections = _naturalness_v2_sections(text)
    fingerprints: list[tuple[str, bool, str, bool]] = []
    meta_close_sections: list[int] = []
    speaker_final_sections: list[int] = []
    abstract_close_sections: list[int] = []

    for section in sections:
        sentences = list(section["sentences"])
        ending_window = "".join(sentences[-2:]) if sentences else ""
        meta_close = any(phrase in ending_window for phrase in _META_SUMMARY_PHRASES)
        speaker_position = _naturalness_v2_speaker_position(sentences)
        abstract_close = bool(
            any(term in ending_window for term in _ABSTRACT_CLOSING_TERMS)
            and not re.search(r"\d|https?://|[A-Za-z]{2,}", ending_window)
        )
        sentence_bucket = "1" if len(sentences) <= 1 else "2" if len(sentences) == 2 else "3+"
        fingerprints.append((sentence_bucket, meta_close, speaker_position, abstract_close))
        if meta_close:
            meta_close_sections.append(int(section["index"]))
        if speaker_position == "final":
            speaker_final_sections.append(int(section["index"]))
        if abstract_close:
            abstract_close_sections.append(int(section["index"]))

    signals: list[dict[str, Any]] = []
    repeated_fingerprints = [
        (fingerprint, count)
        for fingerprint, count in Counter(fingerprints).items()
        if count >= 3 and (fingerprint[1] or fingerprint[2] != "none" or fingerprint[3])
    ]
    if repeated_fingerprints:
        signals.append(
            {
                "code": "section_structure_repetition",
                "severity": "P2",
                "sections": [int(section["index"]) for section in sections],
                "detail": "3つ以上の節で同じ終わり方・話者位置・文数帯が反復しています。",
            }
        )
    if len(meta_close_sections) >= 3:
        signals.append(
            {
                "code": "uniform_conclusion_cadence",
                "severity": "P2",
                "sections": meta_close_sections,
                "detail": "3つ以上の節末でメタ要約から結論へ進む同じリズムが反復しています。",
            }
        )
    if len(speaker_final_sections) >= 3:
        signals.append(
            {
                "code": "speaker_voice_position_repetition",
                "severity": "P2",
                "sections": speaker_final_sections,
                "detail": "3つ以上の節で話者判断が最終文の同じ位置に置かれています。",
            }
        )
    if len(abstract_close_sections) >= 3:
        signals.append(
            {
                "code": "abstract_closing_cluster",
                "severity": "P3",
                "sections": abstract_close_sections,
                "detail": "複数節が抽象的な判断語で閉じています。",
            }
        )

    repair_required = any(row["severity"] in {"P1", "P2"} for row in signals)
    return {
        "signals": signals,
        "repair_required": repair_required,
        "advisory_only": bool(signals) and not repair_required,
        "hard_block": False,
        "blocking_authority": "none",
    }


def build_targeted_naturalness_repair_guidance(article_text: str) -> str:
    """Return issue-specific guidance only for an already-authorized retry."""
    diagnostics = editorial_naturalness_v2_diagnostics(article_text)
    if not diagnostics.get("repair_required"):
        return ""

    rows = []
    for signal in diagnostics.get("signals") or []:
        if signal.get("severity") not in {"P1", "P2"}:
            continue
        code = str(signal.get("code") or "").strip()
        instruction = _NATURALNESS_REPAIR_GUIDANCE.get(code)
        if instruction:
            rows.append(f"・{code}: {instruction}")
    if not rows:
        return ""

    preservation = [
        "Fact / Evidence / Decisionの意味を変えない。",
        "数字・主体・時制・Source Boundary・required_qualifiersを保持する。",
        "情報量を減らさず、新しい事実・因果・体験を追加しない。",
        "問題が検出された文章の運びだけを局所的に再編集する。",
    ]
    return "\n".join(
        ["【Editorial Naturalness v2｜局所修正】", *rows, "【Preservation Contract】"]
        + [f"・{row}" for row in preservation]
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
