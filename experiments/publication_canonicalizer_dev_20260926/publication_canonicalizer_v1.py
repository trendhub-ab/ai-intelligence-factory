"""Stage 4 deterministic Publication Canonicalizer v1.

Experiment-only, Pure Python, zero provider/network calls.

Purpose:
- convert an already-structured AIIF record into a publication-safe input surface;
- preserve Evidence / Decision / Score / URLs;
- add no topic facts or performance claims;
- only normalize presentation contracts, bound unsupported assertion strength,
  simplify implementation-detail clusters, and add stable terminology bridges.

This file is deliberately outside Production.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


SCHEMA = "aiif_local_writer_snapshot_v1"

# Fields rendered by Local Writer v3. source_summary is intentionally not
# stylistically rewritten because it also acts as evidence context.
READER_FIELDS = (
    "reader_title",
    "what",
    "why_important",
    "decision_reason",
    "action",
    "primary_risk",
    "best_for",
    "avoid_for",
)

# Existing Production Fact contract rejects these when they are adopted without
# supporting evidence. Canonicalization always weakens/removes the assertion;
# it never upgrades it.
HYPE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"最後の砦", "選択肢"),
    (r"最後の防衛線", "選択肢"),
    (r"必須インフラ", "基盤候補"),
    (r"一択", "候補"),
    (r"圧倒的", ""),
    (r"劇的に?", ""),
    (r"革命的", "大きな"),
    (r"ゲームチェンジャー", "変化要因"),
    (r"パラダイムシフトと言える", "変化として検討できる"),
    (r"業界標準である", ""),
    (r"業界標準の", ""),
    (r"デファクトスタンダードである", ""),
    (r"デファクトスタンダードの", ""),
)

# Stable language/format definitions only. These are terminology bridges, not
# article claims. They are inserted only where the token already exists.
TERM_BRIDGES: tuple[tuple[str, str], ...] = (
    ("PDF", "文書ファイル形式"),
    ("TTS", "音声合成"),
    ("GCC", "C言語向けコンパイラ"),
    ("NX", "実行不可属性"),
    ("OS", "基本ソフト"),
    ("MSVC", "C/C++コンパイラ"),
    ("DNS", "名前解決の仕組み"),
    ("QA", "品質保証"),
    ("IT", "情報システム"),
)

ROI_RE = re.compile(r"\bROI\b|投資対効果|return on investment", re.I)
MEASURED_ROI_RE = re.compile(
    r"(?:測定|計測|評価|推定|算出|報告).{0,40}(?:ROI|投資対効果)|"
    r"(?:ROI|投資対効果).{0,40}(?:測定|計測|評価|推定|算出|報告)",
    re.I,
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_title(title: str) -> str:
    value = _clean(title).strip('"')
    if not value:
        return value
    if value.endswith("?"):
        return value[:-1] + "？"
    if value.endswith("!"):
        return value[:-1] + "。"
    if value.endswith("！"):
        return value[:-1] + "。"
    if value.endswith(("。", "？")):
        return value
    return value + "。"


def _weaken_hype(text: str) -> str:
    value = _clean(text)
    for pattern, replacement in HYPE_REPLACEMENTS:
        value = re.sub(pattern, replacement, value, flags=re.I)
    # Do not let removing an intensifier create awkward double spaces.
    return re.sub(r"\s+", " ", value).strip()


def _strip_dense_examples(text: str) -> str:
    """Drop only parenthetical implementation/example lists.

    The generic category immediately before the parentheses remains, so the
    semantic claim survives while optional brand/acronym density is removed.
    """
    value = str(text or "")
    pattern = re.compile(
        r"(?P<prefix>(?:モデル|ツール|ライブラリ|実装|方式|環境|技術|サービス))"
        r"（(?P<body>[^（）]{1,90})）"
    )

    def repl(match: re.Match[str]) -> str:
        body = match.group("body")
        technical_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_.+-]{1,}\b", body)
        is_list = bool(re.search(r"[,、/]|(?:など|等)", body))
        if is_list and len(technical_tokens) >= 2:
            return match.group("prefix")
        return match.group(0)

    return pattern.sub(repl, value)


def _normalize_version_terms(text: str, evidence_text: str) -> str:
    value = str(text or "")
    if "V2" in value and "V3" in value and re.search(r"V2.{0,80}V3|V3.{0,80}V2", evidence_text, re.S):
        value = re.sub(r"Manifest\s*V2", "Manifest V2（旧仕様）", value)
        value = re.sub(r"Manifest\s*V3", "Manifest V3（新仕様）", value)
    value = re.sub(r"標準C11/C17/C23準拠", "C言語の複数の標準版への準拠", value)
    return value


def _bridge_terms(fields: dict[str, str]) -> dict[str, str]:
    """Explain the first reader-facing standalone occurrence of each stable term."""
    out = dict(fields)
    for token, explanation in TERM_BRIDGES:
        explained = False
        pattern = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(token)}(?![A-Za-z0-9])")
        for key in ("what", "why_important", "decision_reason", "action", "primary_risk", "best_for", "avoid_for"):
            value = out.get(key, "")
            if not value:
                continue
            if re.search(rf"(?<![A-Za-z0-9-]){re.escape(token)}\s*[（(]", value):
                explained = True
                break
            if not explained and pattern.search(value):
                out[key] = pattern.sub(f"{token}（{explanation}）", value, count=1)
                explained = True
                break
    return out


def _bound_unmeasured_roi(fields: dict[str, str], source_summary: str) -> dict[str, str]:
    evidence = _clean(source_summary)
    if not ROI_RE.search("\n".join(fields.values())):
        return fields
    if ROI_RE.search(evidence) and MEASURED_ROI_RE.search(evidence):
        return fields

    out = dict(fields)
    for key, value in list(out.items()):
        if not ROI_RE.search(value):
            continue
        sentences = re.split(r"(?<=[。！？])", value)
        rewritten: list[str] = []
        for sentence in sentences:
            if not sentence.strip():
                continue
            if ROI_RE.search(sentence):
                rewritten.append("投資対効果は、この根拠だけでは断定せず個別に検証します。")
            else:
                rewritten.append(sentence.strip())
        out[key] = "".join(rewritten)
    return out


def _normalize_negative_urgency(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"直ちに影響はありません", "当面の直接影響はありません", value)
    value = re.sub(r"今すぐ([^。]{0,50})必要はありません", r"現時点で\1必要はありません", value)
    value = re.sub(r"今すぐ([^。]{0,50})必要がない", r"現時点で\1必要がない", value)
    return value


def _bound_low_score_action(action: str, decision: str, score: int) -> str:
    value = _clean(action)
    if decision in {"WATCH", "WAIT"} and score <= 69:
        if not re.search(r"限定|小さく|PoC|比較(?:テスト|検証)|検証環境|回帰テスト|CI", value, re.I):
            return "限定的な検証として、" + value
    return value


def canonicalize(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")

    out = deepcopy(dict(snapshot))
    original_case = _clean(out.get("case_id"))
    canonical_id = _clean(out.get("canonical_entity_id"))
    out["storage_case_id"] = original_case
    # Layout/presentation should be stable by canonical entity, not Notion page id.
    if canonical_id:
        out["case_id"] = canonical_id

    out["reader_title"] = _normalize_title(str(out.get("reader_title") or ""))

    fields = {key: _clean(out.get(key)) for key in READER_FIELDS if key != "reader_title"}
    evidence_text = "\n".join(
        _clean(out.get(key))
        for key in ("source_summary", "what", "why_important", "decision_reason", "primary_risk")
    )

    for key, value in list(fields.items()):
        value = _weaken_hype(value)
        value = _strip_dense_examples(value)
        value = _normalize_version_terms(value, evidence_text)
        value = _normalize_negative_urgency(value)
        fields[key] = value

    fields = _bound_unmeasured_roi(fields, str(out.get("source_summary") or ""))
    fields = _bridge_terms(fields)

    decision = _clean(out.get("decision")).upper()
    score = int(out.get("decision_score") or 0)
    fields["action"] = _bound_low_score_action(fields.get("action", ""), decision, score)

    # Series suffixes are presentation metadata, not part of the decision claim.
    name = _clean(out.get("name"))
    name = re.sub(r"\s+(?:II|III|IV)$", "", name)
    out["name"] = name

    out.update(fields)
    out["canonicalizer_version"] = "stage4_v1"
    return out
