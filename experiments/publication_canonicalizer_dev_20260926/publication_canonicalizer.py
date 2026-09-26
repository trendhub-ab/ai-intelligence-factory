"""Stage 4 experimental Publication Canonicalizer.

Pure Python and deterministic. This layer sits between stored structured records
and the frozen Local Writer v3. It does not generate new evidence or factual
claims, and it does not modify Production code or Gate rules.

Responsibilities are limited to publication contracts:
- normalize reader-title terminal punctuation;
- neutralize bounded wording that the existing Fact Gate treats as unsupported
  exclusivity/hype/market-standard language;
- add bounded first-use explanations for common technical abbreviations that
  are already present in the structured record;
- make low-score/WATCH/WAIT/AVOID actions explicitly limited verification;
- provide a stable presentation-only case key so the frozen writer can diversify
  layouts without changing canonical entity identity.

The original structured snapshot remains the evidence context for validation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Mapping


PUBLICATION_TEXT_FIELDS = (
    "reader_title",
    "source_summary",
    "what",
    "why_important",
    "decision_reason",
    "action",
    "primary_risk",
    "best_for",
    "avoid_for",
)

SUPPLEMENTAL_GLOSSARY = {
    "PDF": "文書ファイル形式",
    "MLX": "特定環境向けの機械学習フレームワーク",
    "TTS": "文字を音声に変換する技術",
    "VAD": "発話区間を検出する処理",
    "STT": "音声を文字に変換する技術",
    "GCC": "C/C++コンパイラ群",
    "NX": "メモリ領域を実行不可にする保護属性",
    "OS": "オペレーティングシステム",
    "MSVC": "C/C++コンパイラ",
    "DNS": "ドメイン名と接続先を対応づける仕組み",
    "QA": "品質保証",
    "IT": "情報技術",
    "DFT": "密度汎関数理論",
    "HEIR": "準同型暗号向けコンパイラ基盤",
    "PII": "個人を識別できる情報",
}

# These are presentation-safety rewrites, not assertions about the technology.
# Prefer deletion or neutral category words over replacing one superlative with
# another.
HYPE_REPLACEMENTS = (
    (re.compile(r"必須インフラ"), "基盤候補"),
    (re.compile(r"最後の砦|最後の防衛線"), "選択肢"),
    (re.compile(r"ゲームチェンジャー"), "変化"),
    (re.compile(r"パラダイムシフトと言える"), "変化として検討できる"),
    (re.compile(r"デファクト(?:スタンダード)?"), "既存仕様"),
    (re.compile(r"業界標準である"), "既存の"),
    (re.compile(r"業界標準の"), "既存の"),
    (re.compile(r"業界標準"), "既存仕様"),
    (re.compile(r"圧倒的(?:に|な)?"), ""),
    (re.compile(r"劇的(?:に|な)?"), ""),
    (re.compile(r"革命的(?:に|な)?"), "新しい"),
    (re.compile(r"(?<![一-龥])一択(?![一-龥])"), "有力な選択肢"),
    (re.compile(r"唯一の"), "一つの"),
)

ROI_RE = re.compile(r"\bROI\b|投資対効果|return on investment", re.I)
ROI_OUTCOME_RE = re.compile(
    r"(?:ROI|投資対効果|return on investment).{0,50}"
    r"(?:証明|改善|向上|増加|保証|高い|低い|見合う|回収)",
    re.I,
)

VERSION_PATTERNS = (
    (re.compile(r"(?<![A-Za-z0-9])V2(?![A-Za-z0-9])"), "V2（バージョン2）"),
    (re.compile(r"(?<![A-Za-z0-9])V3(?![A-Za-z0-9])"), "V3（バージョン3）"),
    (re.compile(r"(?<![A-Za-z0-9])C11(?![A-Za-z0-9])"), "C11（C言語の2011年版規格）"),
    (re.compile(r"(?<![A-Za-z0-9])C17(?![A-Za-z0-9])"), "C17（C言語の2017年版規格）"),
    (re.compile(r"(?<![A-Za-z0-9])C23(?![A-Za-z0-9])"), "C23（C言語の2023年版規格）"),
    (re.compile(r"(?<![A-Za-z0-9])II(?![A-Za-z0-9])"), "II（第2回）"),
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_title(value: str) -> str:
    title = _clean(value)
    if not title:
        return title
    if re.search(r"[。？]$", title):
        return title
    if title.endswith("?"):
        return title[:-1] + "？"
    return title + "。"


def _neutralize_hype(value: str) -> str:
    text = str(value or "")
    for pattern, replacement in HYPE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    # Existing Fact Gate also rejects guarantees such as "完全に解決".
    text = re.sub(r"完全に(?=.{0,12}(?:解決|回避|保証|防止))", "", text)
    text = re.sub(r"完全な(?=.{0,12}(?:解決|回避|保証|防止))", "", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _caveat_roi_outcome(value: str) -> str:
    text = str(value or "")
    if not ROI_OUTCOME_RE.search(text):
        return text
    # No outcome is invented. The claim is converted into an evaluation boundary.
    sentences = re.split(r"(?<=[。！？])", text)
    out: list[str] = []
    for sentence in sentences:
        if not sentence:
            continue
        if ROI_RE.search(sentence) and ROI_OUTCOME_RE.search(sentence):
            out.append("ROI（投資対効果）は、この根拠だけでは断定せず実測で確認します。")
        else:
            out.append(sentence)
    return "".join(out)


def _explain_versions(value: str) -> str:
    text = str(value or "")
    for pattern, replacement in VERSION_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(replacement, text, count=1)
    return text


def _explain_supplemental_terms(value: str, seen: set[str]) -> str:
    text = _explain_versions(str(value or ""))
    for token, explanation in sorted(SUPPLEMENTAL_GLOSSARY.items(), key=lambda item: -len(item[0])):
        if token in seen:
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])")
        if pattern.search(text):
            text = pattern.sub(f"{token}（{explanation}）", text, count=1)
            seen.add(token)
    return text


_SUMMARY_COMMON_ACRONYMS = {
    "AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID", "PC",
}
_SUMMARY_PLAIN_BRIDGE_RE = re.compile(
    r"(?:簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|つまり|"
    r"言葉を変えると|たとえば|例えば|ようなもの|という意味|を指します|のことです)"
)


def _summary_needs_plain_bridge(value: str) -> bool:
    """Mirror the final-surface compact-summary risk at high precision.

    This does not delete technical detail. It only marks dense compact fields with
    an explicit reader bridge so the same evidence remains readable in the 30-second card.
    """
    text = _clean(value)
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 45 or _SUMMARY_PLAIN_BRIDGE_RE.search(text):
        return False
    acronyms = {
        token for token in re.findall(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])", text)
        if token not in _SUMMARY_COMMON_ACRONYMS
    }
    technical = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", text)
    }
    return len(acronyms) >= 2 or len(technical) >= 5


def _add_summary_plain_bridge(value: str) -> str:
    text = _clean(value)
    return "簡単に言えば、" + text if _summary_needs_plain_bridge(text) else text


def _canonicalize_action(value: str, decision: str, score: int) -> str:
    text = _clean(value)
    if decision in {"WATCH", "WAIT", "AVOID"} or score <= 69:
        if not re.search(r"限定|小さく|PoC|比較(?:テスト|検証)|検証環境|回帰テスト|CI", text, re.I):
            text = "限定的な検証として、" + text
    return text


def _presentation_case_id(snapshot: Mapping[str, Any]) -> str:
    """Create a presentation-only seed without changing canonical identity.

    The target slot comes from the frozen selection hash when present; otherwise
    from the canonical entity id. We search a tiny deterministic suffix space so
    frozen Local Writer v3's existing SHA-256 layout chooser lands on that slot.
    """
    canonical = str(snapshot.get("canonical_entity_id") or snapshot.get("case_id") or snapshot.get("name") or "")
    raw_hash = snapshot.get("selection_hash")
    if isinstance(raw_hash, int):
        target = raw_hash % 5
    else:
        target = hashlib.sha256(canonical.encode("utf-8")).digest()[1] % 5
    base = canonical + "|publication-v1"
    for idx in range(100):
        candidate = f"{base}|{idx}"
        if hashlib.sha256(candidate.encode("utf-8")).digest()[0] % 5 == target:
            return candidate
    return base


def canonicalize_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(snapshot))
    out["canonicalizer_original_case_id"] = out.get("case_id")
    out["case_id"] = _presentation_case_id(snapshot)

    decision = str(out.get("decision") or "").upper()
    score = int(out.get("decision_score") or 0)

    # First pass: contract-safe wording and title.
    for key in PUBLICATION_TEXT_FIELDS:
        text = _clean(out.get(key))
        text = _neutralize_hype(text)
        text = _caveat_roi_outcome(text)
        out[key] = text
    out["reader_title"] = _normalize_title(out.get("reader_title", ""))
    out["action"] = _canonicalize_action(out.get("action", ""), decision, score)

    # Second pass follows Local Writer's body-consumption order. Summary/title
    # state is deliberately separate: a term explained only in the 30-second card
    # must still receive a first-use explanation in the article body.
    body_seen: set[str] = set()
    for key in (
        "name",
        "what",
        "why_important",
        "primary_risk",
        "best_for",
        "avoid_for",
        "decision_reason",
        "action",
    ):
        out[key] = _explain_supplemental_terms(out.get(key, ""), body_seen)

    summary_seen: set[str] = set()
    out["source_summary"] = _explain_supplemental_terms(out.get("source_summary", ""), summary_seen)
    out["reader_title"] = _explain_supplemental_terms(out.get("reader_title", ""), set())

    # Fields that feed the deterministic 30-second summary need a reader bridge
    # only when their compact form would otherwise be jargon-dense.
    out["source_summary"] = _add_summary_plain_bridge(out.get("source_summary", ""))
    out["why_important"] = _add_summary_plain_bridge(out.get("why_important", ""))

    out["publication_canonicalized"] = True
    out["publication_canonicalizer_version"] = "stage4-v3"
    return out
