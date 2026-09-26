"""Local Writer v4 — evidence-safe reader accessibility repair.

Pure Python, zero network/provider calls. This version tests whether a small,
general set of deterministic editorial/compiler rules can generalize across the
five heterogeneous snapshots without changing any Production Gate.

Compared with the frozen v3:
- keep the same deterministic source-role and decision structure;
- add a first-use subject bridge sourced only from the stored source_summary;
- add one layout-varied conversational foothold so a non-engineer can identify
  what the named subject is before technical detail;
- keep bounded glossary handling, limitation adjacency, and ROI safety;
- add no provider calls and no new source facts.

No Evidence, Decision, Score, URL, Production code, or Gate rule is changed.
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
    "PR": "変更提案",
    "MCP": "AIと外部ツールやデータを接続する共通規格",
}

COMPOUND_GLOSSARY = {
    "Model Context Protocol (MCP)": "AIと外部ツールやデータを接続する共通規格",
    "Agent Skills": "AIに特定作業の手順や知識を追加する仕組み",
    "CI/CD": "変更を自動検証・配布する仕組み",
    "PoC": "限定的な概念実証",
}

ROI_OUTCOME_RE = re.compile(
    r"(?:ROI|投資対効果).{0,40}(?:証明|改善|向上|増加|高い|低い|保証|確実|見合う)",
    re.I,
)


class SnapshotError(ValueError):
    pass


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema") != SCHEMA:
        raise SnapshotError(f"schema must be {SCHEMA}")
    contaminated = sorted(FORBIDDEN_BODY_FIELDS & set(snapshot))
    if contaminated:
        raise SnapshotError("existing prose is forbidden: " + ", ".join(contaminated))
    missing = [key for key in REQUIRED_FIELDS if snapshot.get(key) in (None, "", [])]
    if missing:
        raise SnapshotError("missing structured fields: " + ", ".join(missing))
    decision = str(snapshot["decision"]).upper()
    if decision not in DECISION_PHRASES:
        raise SnapshotError("unsupported decision code")
    score = int(snapshot["decision_score"])
    if not 1 <= score <= 100:
        raise SnapshotError("decision_score must be 1..100")
    urls = snapshot["evidence_urls"]
    if not isinstance(urls, list) or not urls:
        raise SnapshotError("evidence_urls must be a non-empty list")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _layout_id(snapshot: Mapping[str, Any]) -> int:
    seed = str(snapshot.get("case_id") or snapshot.get("canonical_entity_id") or snapshot["name"])
    return hashlib.sha256(seed.encode("utf-8")).digest()[0] % 5


def _reduce_dense_inline_code(text: str) -> str:
    """Keep the decision while avoiding implementation syntax becoming the article's subject.

    This rule is content-agnostic: only backtick spans with several uppercase
    command-like tokens or unusually long syntax are abstracted. Short named
    features remain visible.
    """
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        upper = re.findall(r"(?<![A-Za-z0-9])[A-Z]{2,}(?![A-Za-z0-9])", inner)
        if len(upper) >= 2 or len(inner) > 44:
            return "保存済みActionにある実装構文"
        return inner

    return re.sub(r"`([^`\n]+)`", repl, str(text or ""))


def _gloss(text: str, seen: set[str]) -> str:
    value = _reduce_dense_inline_code(_clean(text))
    for token, explanation in COMPOUND_GLOSSARY.items():
        if token in value and token not in seen:
            value = value.replace(token, f"{token}（{explanation}）", 1)
            seen.add(token)
            if token == "Model Context Protocol (MCP)":
                seen.add("MCP")
    for token, explanation in sorted(GLOSSARY.items(), key=lambda item: -len(item[0])):
        if token in seen:
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])")
        if pattern.search(value):
            value = pattern.sub(f"{token}（{explanation}）", value, count=1)
            seen.add(token)
    return value


def _safe_why(text: str, seen: set[str]) -> str:
    raw = _clean(text)
    # If an unsupported outcome sentence is replaced, do not mark terminology
    # that disappears with that sentence as already explained. Later surviving
    # occurrences must still receive their first-use bridge.
    if ROI_OUTCOME_RE.search(raw):
        return (
            "この情報は、導入価値を判断する背景材料として扱います。"
            "成果を先に決めつけず、実際の比較で使える判断材料が増えるかを確かめます。"
        )
    return _gloss(raw, seen)


def _source_role(snapshot: Mapping[str, Any]) -> str:
    source = str(snapshot["source"])
    if source == "GitHub":
        return "公開されているコードを、製品扱いせず検証材料としてどこまで使うかを決める話"
    if source == "OfficialVendor":
        return "公式に提供されているサービスを、契約前に小さく比較する話"
    if source == "HackerNews":
        return "開発で話題になった構成を、そのまま信じず試す範囲を決める話"
    if source == "ArXiv":
        return "研究で示された手法を、すぐ本番へ入れず設計判断としてどう持ち帰るかを見る話"
    return "一次情報から、次に何を試すかを決める話"


def _subject_label(snapshot: Mapping[str, Any]) -> str:
    """Return a short display label without asserting what the subject does."""
    name = _clean(snapshot["name"])
    parts = re.split(r"\s+[–—]\s+|[：:]", name, maxsplit=1)
    subject = _clean(parts[0] if parts else name)
    if not subject or len(subject) > 48:
        return "この対象"
    return subject


def _reader_subject_bridge(snapshot: Mapping[str, Any], layout: int) -> str:
    """Give non-engineers a first-use foothold using only stored structured text."""
    subject = _subject_label(snapshot)
    summary = _gloss(snapshot["source_summary"], set())
    if re.search(r"[A-Za-z]", subject):
        label = f"今回の検証対象（{subject}）"
    else:
        label = f"今回の検証対象である{subject}"
    leads = [
        "名前だけでは少し分かりにくいですよね。",
        "まず「結局、何をするもの？」と感じませんか。",
        "名前だけで役割まで想像するのは難しいですよね。",
        "ここで「何の話？」と思いませんか。",
        "最初に「何のためのもの？」から確認したくなりますよね。",
    ]
    return f"{leads[layout]}{label}について、一次情報で確認できる説明はこうです。{summary}"


def _opening(snapshot: Mapping[str, Any], layout: int) -> list[str]:
    name = _clean(snapshot["name"])
    role = _source_role(snapshot)
    subject_bridge = _reader_subject_bridge(snapshot, layout)
    openings = {
        0: [
            f"{name}を自社で使うなら、最初に決めたいのは「採用するか」ではなく「どこまで試すか」です。",
            f"簡単に言えば、今回は{role}です。",
            "機能名を追う前に、判断に必要な事実と制約を分けて見ます。",
            subject_bridge,
        ],
        1: [
            f"仕事で{name}を検討するとき、知りたいのは機能の数より、任せてよい範囲です。",
            f"要するに、今回は{role}です。",
            "ここでは、使える点と、まだ確かめるべき点を同じ重さで扱います。",
            subject_bridge,
        ],
        2: [
            f"{name}。名前は少し難しく見えても、使う側の問いは単純です。",
            "自社の判断が何か変わるのか。それとも、まだ様子を見るべきなのか。",
            f"平たく言えば、今回は{role}です。",
            subject_bridge,
        ],
        3: [
            "新しい技術やサービスを見ると、つい機能一覧から読み始めたくなります。",
            f"でも、{name}で先に見るべきなのは、自社の判断が本当に変わるかです。",
            f"一言で言えば、{role}です。",
            subject_bridge,
        ],
        4: [
            f"もし{name}を明日から使うなら、どこを最初に確認するでしょうか。",
            f"簡単に言えば、{role}です。",
            "そこで、できること、制約、次の一手の順に整理します。",
            subject_bridge,
        ],
    }
    return openings[layout]


def _plain_bridge(layout: int) -> str:
    rows = [
        "ここで重要なのは、用語を全部覚えることではありません。自社で何を確認すれば次の判断へ進めるか、その順番を見失わないことです。",
        "読み方の軸はシンプルです。便利そうかどうかではなく、どの条件なら試せて、どの条件なら待つべきかを分けます。",
        "技術の細部は必要になった段階で追えば十分です。先に、判断を変える事実と、変えない事実を分けておきます。",
        "ここでは説明を増やすより、意思決定に必要な境界をはっきりさせます。試す範囲が見えれば、次の検証も小さくできます。",
        "大事なのは、良さそうな点だけを拾わないことです。使える場面と使わない場面を同時に置くと、判断がかなり楽になります。",
    ]
    return rows[layout]


def _close_bridge(layout: int) -> str:
    rows = [
        "この順番なら、期待だけで広げず、必要な確認を先に終えられます。",
        "全面採用の答えを急がず、小さな検証で次の材料を増やす方が安全です。",
        "今決めるのは最終結論ではなく、次に確かめる一点です。それなら根拠の範囲を越えません。",
        "結論を大きくする必要はありません。保存済みの根拠から、次の一手だけを具体化します。",
        "採用か不採用かを一度で決めるより、制約を残したまま次の検証へ進む方が現実的です。",
    ]
    return rows[layout]


def _sections(snapshot: Mapping[str, Any], layout: int) -> list[tuple[str, list[str]]]:
    seen: set[str] = set()
    what = _gloss(snapshot["what"], seen)
    why = _safe_why(snapshot["why_important"], seen)
    risk = _gloss(snapshot["primary_risk"], seen)
    best = _gloss(snapshot["best_for"], seen)
    avoid = _gloss(snapshot["avoid_for"], seen)
    reason = _gloss(snapshot["decision_reason"], seen)
    action = _gloss(snapshot["action"], seen)
    phrase = DECISION_PHRASES[str(snapshot["decision"]).upper()]
    bridge = _plain_bridge(layout)
    close = _close_bridge(layout)

    # Keep an explicit limitation adjacent to the decision in every layout.
    limitation = f"ただし、制約は明確です。{risk}"

    if layout == 0:
        return [
            ("何が確認されたのか", [what, bridge, why]),
            ("使える場所を先に絞る", [f"向いているのは、{best}", f"一方で、向いていないのは、{avoid}"]),
            ("判断と制約をセットで置く", [f"現時点の判断は「{phrase}」。", reason, limitation]),
            ("次にすること", [action, close]),
        ]
    if layout == 1:
        return [
            ("先に判断を置く", [f"結論から言えば「{phrase}」。", reason, limitation]),
            ("その判断の根拠", [what, bridge, why]),
            ("使う場所を選ぶ", [f"相性がよいのは、{best}", f"逆に、向いていないのは、{avoid}"]),
            ("次の検証", [action, close]),
        ]
    if layout == 2:
        return [
            ("まず何の話か", [what, bridge]),
            ("なぜ見る価値があるのか", [why]),
            ("誰に効くのか", [f"向いているのは、{best}", f"向いていないのは、{avoid}"]),
            ("判断を強くしすぎない", [f"私なら「{phrase}」を選びます。", reason, limitation]),
            ("次の一手", [action, close]),
        ]
    if layout == 3:
        return [
            ("自社の判断に何が変わるか", [why, bridge]),
            ("仕組みを必要な分だけ見る", [what]),
            ("本番へ急がない理由", [limitation]),
            ("試すならここまで", [f"判断は「{phrase}」。", reason, action, close]),
        ]
    return [
        ("数字や主張より先に見ること", [what, bridge, why]),
        ("研究結果と実運用は分ける", [limitation]),
        ("向く組織、向かない組織", [f"向いているのは、{best}", f"向いていないのは、{avoid}"]),
        ("持ち帰る設計判断", [reason]),
        ("次の一手", [f"現時点の距離感は「{phrase}」。", action, close]),
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
    lines: list[str] = []
    for idx, paragraph in enumerate(_opening(snapshot, layout)):
        lines.append(paragraph)
        if idx != len(_opening(snapshot, layout)) - 1:
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
