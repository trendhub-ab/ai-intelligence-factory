"""Provider-free Local Writer v2 for the heterogeneous five-article experiment.

The v2 experiment fixes only Writer-side generalization failures discovered by the
unmodified v1 batch probe:
- reader accessibility / jargon translation
- opening decision accessibility
- cross-article structural fingerprinting

It does not weaken or bypass any production Gate. Existing article prose is still
forbidden input. All factual sentences originate from the structured AIIF snapshot;
editorial glue is deterministic and claim-neutral.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

SCHEMA = "aiif_local_writer_snapshot_v1"

REQUIRED_FIELDS = (
    "canonical_entity_id", "name", "reader_title", "source", "source_summary",
    "what", "why_important", "decision", "decision_score", "decision_reason",
    "action", "primary_risk", "best_for", "avoid_for", "evidence_urls",
)
FORBIDDEN_BODY_FIELDS = {
    "article", "article_body", "body", "clean_manuscript",
    "existing_article", "note_draft", "previous_article",
}

DECISION_PHRASES = {
    "NOW": "今すぐ着手する",
    "TRY": "限定した範囲で試す",
    "WATCH": "新しい一次情報が出るまで待ち、出た時点で再評価する",
    "WAIT": "条件が整うまで待つ",
    "AVOID": "現時点では採用を見送る",
}

_COMMON_ACRONYMS = {
    "AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID",
}
_UNKNOWN_ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


class SnapshotError(ValueError):
    pass


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema") != SCHEMA:
        raise SnapshotError(f"schema must be {SCHEMA}")
    contaminated = sorted(FORBIDDEN_BODY_FIELDS & set(snapshot))
    if contaminated:
        raise SnapshotError("existing prose is forbidden: " + ", ".join(contaminated))
    missing = [
        key for key in REQUIRED_FIELDS
        if key not in snapshot or snapshot.get(key) in (None, "", [])
    ]
    if missing:
        raise SnapshotError("missing structured fields: " + ", ".join(missing))
    if str(snapshot["decision"]).upper() not in DECISION_PHRASES:
        raise SnapshotError("unsupported decision code")
    score = int(snapshot["decision_score"])
    if not 1 <= score <= 100:
        raise SnapshotError("decision_score must be 1..100")
    urls = snapshot["evidence_urls"]
    if not isinstance(urls, list) or not urls:
        raise SnapshotError("evidence_urls must be a non-empty list")
    if not all(isinstance(url, str) and url.startswith(("https://", "http://")) for url in urls):
        raise SnapshotError("evidence_urls must contain HTTP(S) strings")


def source_context(snapshot: Mapping[str, Any]) -> str:
    validate_snapshot(snapshot)
    keys = (
        "reader_title", "name", "source_summary", "what", "why_important",
        "decision_reason", "action", "primary_risk", "best_for", "avoid_for",
    )
    rows = [f"{key}: {_clean(snapshot[key])}" for key in keys]
    rows.append("evidence_urls: " + " | ".join(snapshot["evidence_urls"]))
    return "\n".join(rows)


def _unknown_acronyms(text: str) -> list[str]:
    out: list[str] = []
    for match in _UNKNOWN_ACRONYM_RE.finditer(text or ""):
        token = match.group(1)
        if token not in _COMMON_ACRONYMS and token not in out:
            out.append(token)
    return out


def _reader_surface(value: Any) -> str:
    """Compress implementation identifiers without inventing replacement facts."""
    text = _clean(value)

    # Drop acronym-only parentheticals when the Japanese phrase already carries the meaning.
    text = re.sub(
        r"[（(]\s*(?:[A-Z][A-Z0-9-]{1,8})(?:\s*/\s*[A-Z][A-Z0-9-]{1,8})*\s*[）)]",
        "",
        text,
    )

    # Keep readable inline-code payload only when it is not implementation-heavy.
    def code_repl(match: re.Match[str]) -> str:
        payload = match.group(1).strip()
        unknown = _unknown_acronyms(payload)
        if unknown or re.search(r"(?:--|\.\.|[/\\])", payload):
            return ""
        return payload

    text = _INLINE_CODE_RE.sub(code_repl, text)

    # Unknown bare acronyms are implementation labels on the free reader surface.
    # Removing them is a compression operation; the full field remains in MANAGEMENT DATA.
    def acronym_repl(match: re.Match[str]) -> str:
        token = match.group(1)
        return token if token in _COMMON_ACRONYMS else ""

    text = _UNKNOWN_ACRONYM_RE.sub(acronym_repl, text)

    # Repair punctuation left by deterministic identifier compression.
    text = re.sub(r"[「『]\s*[」』]", "", text)
    text = re.sub(r"[（(]\s*[）)]", "", text)
    text = re.sub(r"\s*/\s*(?=[、。])", "", text)
    text = re.sub(r"(?<=、)\s*(?:または|および)\s*(?=[、。])", "", text)
    text = re.sub(r"、\s*、", "、", text)
    text = re.sub(r"\s+([、。！？])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip(" 、")
    return text


def _importance(snapshot: Mapping[str, Any]) -> str:
    """Choose the lower-jargon structured explanation without changing its content."""
    candidates = [
        _clean(snapshot["why_important"]),
        _clean(snapshot["decision_reason"]),
    ]
    def burden(text: str) -> tuple[int, int, int]:
        return (
            len(_unknown_acronyms(text)),
            len(_INLINE_CODE_RE.findall(text)),
            len(text),
        )
    return _reader_surface(min(candidates, key=burden))


def _profile(snapshot: Mapping[str, Any]) -> int:
    source = _clean(snapshot["source"])
    if source == "GitHub":
        return 0
    if source == "HackerNews":
        return 1
    if source == "OfficialVendor":
        return 2
    if source == "ArXiv":
        return 3 + (int(snapshot["decision_score"]) % 2)
    digest = hashlib.sha256(_clean(snapshot["canonical_entity_id"]).encode("utf-8")).digest()
    return digest[0] % 5


def _decision_phrase(snapshot: Mapping[str, Any]) -> str:
    return DECISION_PHRASES[str(snapshot["decision"]).upper()]


def _opening(snapshot: Mapping[str, Any], core: str, importance: str, profile: int) -> list[str]:
    name = _clean(snapshot["name"])
    openings = {
        0: [
            f"{name}を使う側で最初に迷うのは、研究コードをどこまで実務へ持ち込むかでしょうか。",
            f"簡単に言えば、公開情報として確認している内容はこうです。{core}",
            f"自社で判断するなら、重要なのは次の点です。{importance}",
        ],
        1: [
            f"{name}という考え方は、便利そうだから全部まとめる、という話ではありません。",
            f"ひと言で言えば、公開情報として確認している内容はこうです。{core}",
            f"使うなら何を比べるべきか。判断に効くのは次の点です。{importance}",
        ],
        2: [
            f"{name}を導入するかどうかより先に、まず何を観測したいのかを決める必要があります。",
            f"平たく言えば、公開情報として確認している内容はこうです。{core}",
            f"自社で検証するなら、重要なのは次の点です。{importance}",
        ],
        3: [
            f"{name}は専門用語から入るより、運用で何が変わるのかを見る方が理解しやすいテーマです。",
            f"要するに、公開情報として確認している内容はこうです。{core}",
            f"私たちが判断するときに見るべき理由は次の通りです。{importance}",
        ],
        4: [
            f"{name}を今すぐ採用するか、という問いから始める必要はありません。",
            f"一言で言えば、公開情報として確認している内容はこうです。{core}",
            f"まず「何ができ、どこに限界があるか」を分けます。重要性は次の通りです。{importance}",
        ],
    }
    return openings[profile]


def _layout(snapshot: Mapping[str, Any]) -> list[str]:
    validate_snapshot(snapshot)
    profile = _profile(snapshot)
    core = _reader_surface(snapshot["what"])
    importance = _importance(snapshot)
    risk = _reader_surface(snapshot["primary_risk"])
    best_for = _reader_surface(snapshot["best_for"])
    avoid_for = _reader_surface(snapshot["avoid_for"])
    action = _reader_surface(snapshot["action"])
    decision = _decision_phrase(snapshot)

    intro = _opening(snapshot, core, importance, profile)
    source = _clean(snapshot["source"])
    evidence = [f"- {url}" for url in snapshot["evidence_urls"]]

    # Five intentionally different article rhythms. The structure selection is deterministic
    # from source/score, not from a pre-existing manuscript.
    if profile == 0:
        return [
            *intro, "",
            "## 研究コードは「製品」と同じ条件では読まない", "",
            f"ただし、判断には次の制約があります。{risk}", "",
            f"向いているのは、{best_for}", "",
            "## 私なら、使う場所を限定する", "",
            f"現時点の判断は「{decision}」です。", "",
            "私なら、まず必要な範囲だけを検証します。全面採用の判断とは分けます。", "",
            "## 次に確認すること", "",
            (f"具体的には、{action}" if action else "具体的な手順は、対象を限定して再現性を確認します。"), "",
            "### Sources / Evidence", "", f"- 発見経路: {source}", *evidence,
        ]

    if profile == 1:
        return [
            *intro, "",
            "## 先に結論を置く", "",
            f"私なら「{decision}」とします。使える範囲を確かめてから広げる判断です。", "",
            "## 便利さと限界を同時に見る", "",
            f"ただし、次の制約があります。{risk}", "",
            "## 誰に向く話か", "",
            f"向いているのは、{best_for}", "",
            f"逆に、{avoid_for}", "",
            "## 次の一手", "",
            (f"検証するなら、{action}" if action and not _unknown_acronyms(action) else "私なら、まず限定した範囲で比較検証します。"), "",
            "### Sources / Evidence", "", f"- 発見経路: {source}", *evidence,
        ]

    if profile == 2:
        return [
            *intro, "",
            "## 測ることと、成果を約束することは別", "",
            f"ただし、判断には次の制約があります。{risk}", "",
            "## まず合う利用者を絞る", "",
            f"向いているのは、{best_for}", "",
            "## 合わない条件も先に見る", "",
            f"優先度が低いのは、{avoid_for}", "",
            "## 私なら小さく試す", "",
            f"現時点の判断は「{decision}」です。", "",
            (f"次にやることは、{action}" if action else "まず手作業との比較から始めます。"), "",
            "## 続けるかは結果で決める", "",
            "導入そのものを目的にせず、比較結果が判断材料になるかを確認してから継続を決めます。", "",
            "### Sources / Evidence", "", f"- 発見経路: {source}", *evidence,
        ]

    if profile == 3:
        return [
            *intro, "",
            "## 変えるのはモデルだけではない", "",
            f"ただし、現時点では次の制約があります。{risk}", "",
            "## 使う価値があるのはどこか", "",
            f"向いているのは、{best_for}", "",
            "## 使わなくてよいケース", "",
            f"逆に、{avoid_for}", "",
            "## 判断を急がない理由", "",
            f"現時点の判断は「{decision}」です。", "",
            "## 私なら回帰を先に確かめる", "",
            (f"次にやることは、{action}" if action and not _unknown_acronyms(action) else "私なら、まず限定環境で変更前後を比較検証します。"), "",
            "## 見るべきなのは再現性", "",
            "一度うまく動くことより、変更後も重要な挙動が保たれるかを確認してから次へ進みます。", "",
            "### Sources / Evidence", "", f"- 発見経路: {source}", *evidence,
        ]

    return [
        *intro, "",
        "## できること", "",
        core, "",
        "## できないことを先に置く", "",
        f"ただし、次の制約があります。{risk}", "",
        "## 研究結果と本番運用は分ける", "",
        f"向いているのは、{best_for}", "",
        "## 優先度が低いケース", "",
        f"逆に、{avoid_for}", "",
        "## 現時点の判断", "",
        f"私なら「{decision}」とします。", "",
        "## 次に見るポイント", "",
        (f"次にやることは、{action}" if action and not _unknown_acronyms(action) else "私なら、まず設計パターンとして比較・検証します。"), "",
        "## そこで判断を更新する", "",
        "追加の検証結果が揃った時点で、採用するか、待つかをもう一度判断します。", "",
        "### Sources / Evidence", "", f"- 発見経路: {source}", *evidence,
    ]


def render_body(snapshot: Mapping[str, Any]) -> str:
    return "\n".join(_layout(snapshot)).strip() + "\n"


def render_article(snapshot: Mapping[str, Any]) -> str:
    validate_snapshot(snapshot)
    return f"# {_clean(snapshot['reader_title'])}\n\n{render_body(snapshot)}"


def to_pipeline_parsed(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    return {
        "title_text": _clean(snapshot["reader_title"]),
        "note_draft": render_body(snapshot),
        "score": int(snapshot["decision_score"]),
        "decision_text": str(snapshot["decision"]).upper(),
        "decision_reason_text": _clean(snapshot["decision_reason"]),
        "source_summary_text": _clean(snapshot["source_summary"]),
        "what_text": _clean(snapshot["what"]),
        "why_important_text": _clean(snapshot["why_important"]),
        "why_not_important_text": _clean(snapshot["primary_risk"]),
        "action_text": _clean(snapshot["action"]),
        "paradigm_shift_text": "",
        "alternative_comparison_text": "",
        "migration_cost_text": "",
        "future_scenario_text": "",
    }
