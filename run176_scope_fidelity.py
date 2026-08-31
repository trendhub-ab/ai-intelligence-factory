"""Run176 scope-fidelity guardrails derived from Run175 production audit.

Targets narrow, high-confidence semantic overreach that can survive ordinary claim/evidence checks:
1) source-attribution drift: a named historical document is made to say a later protocol name
   that is absent from the document-local evidence;
2) theory-to-practice drift: a pure theorem/proof is described as guaranteeing the correctness,
   reliability, safety, or performance of practical systems.

The layer is zero-API. It does not change Decision Score, Evidence thresholds, article style,
or Gemini request budgets. It only strengthens prompt guidance, Fact Gate validation and
repair instructions.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_INSTALLED_ATTR = "_run176_scope_fidelity_installed"

_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?", re.MULTILINE)
# Do not use Unicode word boundaries around ASCII anchors: Japanese particles are Unicode
# word characters and commonly touch the anchor directly (for example "RFC 1631という").
_RFC_ANCHOR_RE = re.compile(r"(?<![0-9A-Za-z])RFC\s*[- ]?(\d{3,5})(?![0-9A-Za-z])", re.I)
# Deliberately narrow: versioned/well-known protocol names where literal historical attribution
# is materially different from a retrospective explanation.
_PROTOCOL_TOKEN_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:IPv4|IPv6|HTTP/(?:1\.0|1\.1|2|3)|TLS\s*1\.[0-9]|QUIC|WebRTC)(?![0-9A-Za-z])",
    re.I,
)
_RETROSPECTIVE_RE = re.compile(
    r"(?:後に|のちに|その後|後年|現在では|現在でいう|現在でいえば|結果的に|やがて|"
    r"later|subsequently|eventually|today|now known as|what is now)",
    re.I,
)

_THEORY_EVIDENCE_RE = re.compile(
    r"(?:\btheorem\b|\bproof\b|\bconjecture\b|\bmathematic(?:s|al)\b|\bpercolation\b|"
    r"定理|証明|予想|数学|理論物理)",
    re.I,
)
_PRACTICAL_VALIDATION_EVIDENCE_RE = re.compile(
    r"(?:production deployment|deployed in production|field experiment|field study|empirical evaluation|"
    r"real[- ]world evaluation|system benchmark|evaluated on (?:a )?(?:distributed|production) system|"
    r"実運用で検証|本番環境で検証|実システムで評価|実証実験|フィールド実験)",
    re.I,
)
_PRACTICAL_OBJECT_RE = re.compile(
    r"(?:分散システム|実運用|本番環境|実システム|耐障害性|可用性|安全性|セキュリティ|性能|"
    r"アルゴリズムの性能|distributed systems?|production systems?|fault tolerance|reliability|"
    r"availability|security|performance)",
    re.I,
)
_GUARANTEE_RE = re.compile(
    r"(?:正しさ.{0,14}(?:担保|保証|証明)|確かさ.{0,14}(?:担保|保証|証明)|"
    r"(?:担保|保証|証明)された|(?:guarantees?|proves?|establishes?)\s+(?:the\s+)?(?:correctness|reliability|safety|performance))",
    re.I,
)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"\s+", " ", value).strip()


def _sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(str(text or "")) if m.group(0).strip()]


def _source_rfc_windows(source_context: str, number: str, radius: int = 900) -> list[str]:
    """Return RFC-local windows while tolerating RFC1631 / RFC-1631 / RFC 1631 spelling."""
    source = _norm(source_context)
    pattern = re.compile(
        rf"(?<![0-9A-Za-z])RFC\s*[- ]?{re.escape(str(number))}(?![0-9A-Za-z])",
        re.I,
    )
    windows: list[str] = []
    for match in pattern.finditer(source):
        windows.append(source[max(0, match.start() - radius): min(len(source), match.end() + radius)])
    return windows


def _protocol_literal_present(local_evidence: str, token: str) -> bool:
    """Compare protocol literals without treating harmless ASCII spacing as semantic absence."""
    compact_local = re.sub(r"[\s-]+", "", _norm(local_evidence)).lower()
    compact_token = re.sub(r"[\s-]+", "", _norm(token)).lower()
    return bool(compact_token and compact_token in compact_local)


def _is_retrospective_mapping(sentence: str, token_match: re.Match[str], max_gap: int = 14) -> bool:
    """Allow a retrospective marker only when it actually qualifies the protocol mapping.

    A sentence-wide exemption is unsafe: e.g. "現在ではNATが一般的だが、RFC 1631はIPv6を..."
    contains a retrospective word that does not qualify the RFC->IPv6 attribution.  Requiring
    the marker to sit close to the protocol token preserves legitimate "後にIPv6" / "現在でいうIPv6"
    wording without turning unrelated temporal prose into a bypass.
    """
    for marker in _RETROSPECTIVE_RE.finditer(sentence):
        if marker.end() <= token_match.start():
            gap = token_match.start() - marker.end()
        elif token_match.end() <= marker.start():
            gap = marker.start() - token_match.end()
        else:
            gap = 0
        if gap <= max_gap:
            return True
    return False


def historical_source_attribution_failures(article: str, source_context: str) -> list[str]:
    """Reject literal RFC attribution of a protocol/version absent from RFC-local evidence.

    Retrospective wording is allowed only when the temporal marker locally qualifies the
    protocol mapping; unrelated words such as "現在では" elsewhere in the sentence must not
    disable the guard.
    """
    source = _norm(source_context)
    if not article or not source:
        return []
    failures: list[str] = []
    for sentence in _sentences(article):
        anchor_match = _RFC_ANCHOR_RE.search(sentence)
        if not anchor_match:
            continue
        protocol_matches = list(_PROTOCOL_TOKEN_RE.finditer(sentence))
        if not protocol_matches:
            continue
        anchor_number = anchor_match.group(1)
        anchor = f"RFC {anchor_number}"
        windows = _source_rfc_windows(source, anchor_number)
        if not windows:
            continue
        local = "\n".join(windows)
        for token_match in protocol_matches:
            token = token_match.group(0)
            if _is_retrospective_mapping(sentence, token_match):
                continue
            if _protocol_literal_present(local, token):
                continue
            failures.append(
                "historical_source_attribution_drift: "
                f"{anchor} is presented as naming {token}, but that protocol name is absent from document-local evidence; "
                "use the source-era wording or mark the later mapping as retrospective"
            )
    return list(dict.fromkeys(failures))[:4]


def theory_to_practice_failures(article: str, source_context: str) -> list[str]:
    """Reject practical guarantees inferred from theory-only evidence with high precision."""
    evidence = _norm(source_context)
    if not article or not evidence:
        return []
    if not _THEORY_EVIDENCE_RE.search(evidence):
        return []
    if _PRACTICAL_VALIDATION_EVIDENCE_RE.search(evidence):
        return []
    failures: list[str] = []
    for sentence in _sentences(article):
        if not _PRACTICAL_OBJECT_RE.search(sentence) or not _GUARANTEE_RE.search(sentence):
            continue
        failures.append(
            "theory_to_practice_overclaim: pure theoretical/proof evidence is used to guarantee a practical system property "
            f"({sentence[:120]})"
        )
    return list(dict.fromkeys(failures))[:4]


def scope_fidelity_failures(parsed: dict, source_context: str) -> list[str]:
    article = str((parsed or {}).get("note_draft") or "")
    failures: list[str] = []
    failures.extend(historical_source_attribution_failures(article, source_context))
    failures.extend(theory_to_practice_failures(article, source_context))
    return list(dict.fromkeys(failures))[:8]


def install(pipeline_module: Any) -> Any:
    """Install Run176 scope-fidelity wrappers idempotently after Run175."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_prompt = pipeline_module.build_decision_prompt
    original_validate_fact = pipeline_module.validate_fact_gate
    original_build_retry = pipeline_module.build_dynamic_retry_instruction

    def build_prompt_with_scope_fidelity(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        return prompt.rstrip() + (
            "\n\n【出典時点と理論→実務の境界 / Run176】\n"
            "・古いRFC・論文・仕様を説明するとき、後年に定着した製品名・プロトコル名を、当時の資料がその名前で述べたかのように書かないでください。"
            "後世の対応関係を説明する場合は『後に〜として標準化された』『現在でいう〜』など、資料時点の記述と現在の解釈を分離してください。\n"
            "・数学上の定理・証明・理論結果だけを根拠に、実システムの耐障害性・安全性・性能・前提の正しさが『担保された』『保証された』と一般化しないでください。"
            "実運用での検証が一次資料にない場合は『理論的理解が進んだ』『モデル検討の参考になる可能性がある』程度に限定してください。\n"
            "・個人論考・解説記事の歴史的因果（AがBを定着させた等）は、独立した一次資料で確認できない限り、"
            "『筆者は〜と論じている』『〜という見方を提示している』と見解の主体を残してください。\n"
        )

    def validate_fact_with_scope_fidelity(
        parsed: dict,
        repo_name: str,
        source_context: str = "",
        source: str = "",
        evidence_metadata: dict | None = None,
        source_info: dict | None = None,
        freshness: dict | None = None,
        output_truncated: bool = False,
    ):
        ok, failures = original_validate_fact(
            parsed,
            repo_name,
            source_context=source_context,
            source=source,
            evidence_metadata=evidence_metadata,
            source_info=source_info,
            freshness=freshness,
            output_truncated=output_truncated,
        )
        extra = scope_fidelity_failures(parsed, source_context)
        merged = list(dict.fromkeys(list(failures or []) + extra))[:20]
        if extra:
            pipeline_module.logger.warning("[RUN176 SCOPE FIDELITY] failures=%s repo=%s", extra, repo_name)
        return (bool(ok) and not extra), merged

    def build_retry_with_scope_fidelity(reason_rows: list[dict]):
        instruction, sections = original_build_retry(reason_rows)
        messages = "\n".join(str((row or {}).get("message") or "") for row in (reason_rows or []))
        additions: list[str] = []
        if "historical_source_attribution_drift:" in messages:
            additions.append(
                "・historical_source_attribution_driftは該当文だけを修正してください。歴史資料に存在しない後年の名称を資料自身の語彙として帰属させず、"
                "資料時点の表現へ戻すか、『後に〜』『現在でいう〜』と後世の解釈を明示してください。新しい事実は追加しないでください。"
            )
        if "theory_to_practice_overclaim:" in messages:
            additions.append(
                "・theory_to_practice_overclaimは該当文だけを弱めてください。理論結果を実システムの保証へ拡張せず、"
                "『理論的理解が進んだ』『実務影響は未検証／推論』など一次資料の証拠範囲へ戻してください。"
            )
        if additions:
            instruction = instruction.rstrip() + "\n【Run176 Scope Fidelity Patch】\n" + "\n".join(additions) + "\n"
        return instruction, sections

    pipeline_module.build_decision_prompt = build_prompt_with_scope_fidelity
    pipeline_module.validate_fact_gate = validate_fact_with_scope_fidelity
    pipeline_module.build_dynamic_retry_instruction = build_retry_with_scope_fidelity
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
