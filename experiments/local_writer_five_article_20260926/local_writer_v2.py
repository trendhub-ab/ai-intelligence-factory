"""Second-experiment Local Writer v2.

Pure Python, zero network/provider calls. The change from v1 is editorial only:
- explain uncommon decision-relevant acronyms on first occurrence;
- establish an early reader-decision bridge;
- select one of five deterministic narrative layouts to avoid cross-article template fingerprints.

No Evidence, Decision, Score, Action, URL, or Gate rule is changed.
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
    "article", "article_body", "body", "clean_manuscript", "existing_article",
    "note_draft", "previous_article",
}

DECISION_PHRASES = {
    "NOW": "今すぐ着手する",
    "TRY": "限定した範囲で試す",
    "WATCH": "本格導入は急がず、検証材料として追う",
    "WAIT": "条件が整うまで待つ",
    "AVOID": "現時点では採用を見送る",
}

# General editorial glossary, not per-article prose. It only explains the role of
# abbreviations already present in the structured snapshot.
GLOSSARY = {
    "SLA": "サービス保証条件",
    "SDK": "開発用ツール群",
    "RDBMS": "リレーショナルデータベース管理システム",
    "CTO": "技術責任者",
    "PM": "プロジェクト責任者",
    "SEO": "検索エンジン最適化",
    "GEO": "生成AI検索向けの最適化",
    "ROI": "投資対効果",
    "HCL": "ハーネス継続学習",
    "CIS": "セキュリティ基準",
    "ACL": "通信許可ルール",
    "IBN": "意図ベースのネットワーク設計",
    "GIN": "複合値検索向けインデックス",
    "B2B": "法人向け",
    "SLA": "サービス保証条件",
}


class SnapshotError(ValueError):
    pass


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema") != SCHEMA:
        raise SnapshotError(f"schema must be {SCHEMA}")
    contaminated = sorted(FORBIDDEN_BODY_FIELDS & set(snapshot))
    if contaminated:
        raise SnapshotError("existing prose is forbidden: " + ", ".join(contaminated))
    missing = [k for k in REQUIRED_FIELDS if snapshot.get(k) in (None, "", [])]
    if missing:
        raise SnapshotError("missing structured fields: " + ", ".join(missing))
    decision = str(snapshot["decision"]).upper()
    if decision not in DECISION_PHRASES:
        raise SnapshotError("unsupported decision code")
    score = int(snapshot["decision_score"])
    if not 1 <= score <= 100:
        raise SnapshotError("decision_score must be 1..100")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _layout_id(snapshot: Mapping[str, Any]) -> int:
    seed = str(snapshot.get("case_id") or snapshot.get("canonical_entity_id") or snapshot["name"])
    return hashlib.sha256(seed.encode("utf-8")).digest()[0] % 5


def _gloss(text: str, seen: set[str]) -> str:
    value = str(text or "")
    # Explain compound tokens before shorter tokens.
    compound = {
        "CI/CD": "変更を自動検証・配布する仕組み",
        "PoC": "限定的な概念実証",
    }
    for token, explanation in compound.items():
        if token in value and token not in seen:
            value = value.replace(token, f"{token}（{explanation}）", 1)
            seen.add(token)
    for token, explanation in sorted(GLOSSARY.items(), key=lambda x: -len(x[0])):
        if token in seen:
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])")
        if pattern.search(value):
            value = pattern.sub(f"{token}（{explanation}）", value, count=1)
            seen.add(token)
    return value


def _plain_role(snapshot: Mapping[str, Any]) -> str:
    source = str(snapshot["source"])
    decision = str(snapshot["decision"]).upper()
    if source == "GitHub":
        return "公開コードをそのまま製品扱いせず、どこまで検証材料として使うかを決める話"
    if source == "OfficialVendor":
        return "新しいサービスを契約する前に、自社の判断材料が本当に増えるかを確かめる話"
    if source == "HackerNews":
        return "話題の主張をそのまま採用せず、自社で試す範囲を切り分ける話"
    if source == "ArXiv" and decision == "WATCH":
        return "研究成果をすぐ本番へ入れるのではなく、設計思想として何を持ち帰るかを決める話"
    return "一次情報から、次に何を試すかを決める話"


def _opening(snapshot: Mapping[str, Any], layout: int) -> list[str]:
    role = _plain_role(snapshot)
    name = _clean(snapshot["name"])
    if layout == 0:
        return [
            "もしこの情報を自社で使うなら、何をそのまま採用し、どこから検証すべきでしょうか。",
            f"簡単に言えば、今回は「{role}」です。",
            f"対象は{name}。名前や機能の多さより、判断に使える範囲を先に見ます。",
        ]
    if layout == 1:
        return [
            f"仕事で{name}を検討するとき、最初に知りたいのは「使えるか」より「どこまで任せてよいか」です。",
            f"要するに、これは{role}です。",
        ]
    if layout == 2:
        return [
            f"{name}。少し難しそうな名前ですが、使う側の問いは単純です。",
            "自社の仕事に持ち込む価値があるのか。それとも、まだ様子を見るべきなのか。",
            f"平たく言えば、今回は{role}です。",
        ]
    if layout == 3:
        return [
            "新しい技術やサービスを見ると、機能一覧から読み始めたくなります。",
            f"でも、{name}で先に見るべきなのは、自社の判断が何か変わるかです。",
            f"一言で言えば、{role}です。",
        ]
    return [
        f"もし{name}を明日から使うとしたら、どこが一番の確認ポイントになるでしょうか。",
        f"簡単に言えば、{role}です。",
        "そこで、できることと、まだ言えないことを分けて見ます。",
    ]


def _sections(snapshot: Mapping[str, Any], layout: int) -> list[tuple[str, list[str]]]:
    seen: set[str] = set()
    what = _gloss(_clean(snapshot["what"]), seen)
    why = _gloss(_clean(snapshot["why_important"]), seen)
    risk = _gloss(_clean(snapshot["primary_risk"]), seen)
    best = _gloss(_clean(snapshot["best_for"]), seen)
    avoid = _gloss(_clean(snapshot["avoid_for"]), seen)
    reason = _gloss(_clean(snapshot["decision_reason"]), seen)
    action = _gloss(_clean(snapshot["action"]), seen)
    phrase = DECISION_PHRASES[str(snapshot["decision"]).upper()]
    score = int(snapshot["decision_score"])

    # Five different orderings deliberately change paragraph rhythm and heading count.
    if layout == 0:
        return [
            ("何が確認されたのか", [what, why]),
            ("ここで広げすぎない", [risk, f"向いているのは、{best}", f"逆に、{avoid}"]),
            ("私なら次にこうする", [f"保存済みの判断は「{phrase}」。", reason, f"まず行うのは、{action}"]),
        ]
    if layout == 1:
        return [
            ("先に判断を置く", [f"結論から言えば「{phrase}」。", reason]),
            ("その判断の根拠", [what, why]),
            ("使う場所を選ぶ", [f"相性がよいのは、{best}", f"一方で、{avoid}", risk]),
            ("次の検証", [action]),
        ]
    if layout == 2:
        return [
            ("まず何の話か", [what]),
            ("なぜ見る価値があるのか", [why]),
            ("誰に効くのか", [best, avoid]),
            ("ただし、ここが境界", [risk]),
            ("最終的な距離感", [f"私なら「{phrase}」を選びます。", reason, action]),
        ]
    if layout == 3:
        return [
            ("自社の判断に何が変わるか", [why]),
            ("仕組みを必要な分だけ見る", [what]),
            ("本番へ急がない理由", [risk]),
            ("試すならここまで", [f"判断は「{phrase}」。", reason, action]),
        ]
    return [
        ("数字や主張より先に見ること", [what, why]),
        ("研究結果と実運用は分ける", [risk]),
        ("向く組織、向かない組織", [f"向いているのは、{best}", f"向いていないのは、{avoid}"]),
        ("持ち帰る設計判断", [reason]),
        ("次の一手", [f"現時点の距離感は「{phrase}」。", action]),
    ]


def source_context(snapshot: Mapping[str, Any]) -> str:
    validate_snapshot(snapshot)
    keys = (
        "reader_title", "name", "source_summary", "what", "why_important",
        "decision_reason", "action", "primary_risk", "best_for", "avoid_for",
    )
    rows = [f"{key}: {_clean(snapshot[key])}" for key in keys]
    rows.append("evidence_urls: " + " | ".join(snapshot["evidence_urls"]))
    return "\n".join(rows)


def render_body(snapshot: Mapping[str, Any]) -> str:
    validate_snapshot(snapshot)
    layout = _layout_id(snapshot)
    blocks = _opening(snapshot, layout)
    lines: list[str] = []
    # Deliberately alternate paragraph size and endings to avoid run-level template fingerprints.
    for i, paragraph in enumerate(blocks):
        lines.append(paragraph)
        if i != len(blocks) - 1:
            lines.append("")

    for heading, paragraphs in _sections(snapshot, layout):
        lines.extend(["", f"## {heading}", ""])
        for idx, paragraph in enumerate(paragraphs):
            lines.append(paragraph)
            if idx != len(paragraphs) - 1:
                lines.append("")

    lines.extend(["", "### Sources / Evidence", "", f"- 発見経路: {_clean(snapshot['source'])}"])
    lines.extend(f"- {url}" for url in snapshot["evidence_urls"])
    return "\n".join(lines).strip() + "\n"


def render_article(snapshot: Mapping[str, Any]) -> str:
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
