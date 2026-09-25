"""Bounded, provider-free one-article Local Writer experiment.

This module is intentionally pure: it accepts an AIIF structured snapshot and
returns reader-facing Markdown. It performs no network access, provider call,
Notion operation, note operation, file write, or status mutation.

The experiment forbids feeding an existing article body back into the writer.
Only structured Evidence / Decision / Action fields are accepted.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA = "aiif_local_writer_snapshot_v1"

REQUIRED_FIELDS = (
    "canonical_entity_id",
    "name",
    "reader_title",
    "source",
    "source_summary",
    "what",
    "why_important",
    "decision",
    "decision_score",
    "decision_reason",
    "action",
    "primary_risk",
    "best_for",
    "avoid_for",
    "evidence_confidence",
    "production_readiness",
    "evidence_urls",
)

FORBIDDEN_BODY_FIELDS = {
    "article",
    "article_body",
    "body",
    "clean_manuscript",
    "existing_article",
    "note_draft",
    "previous_article",
}

DECISION_PHRASES = {
    "NOW": "今すぐ着手する",
    "TRY": "限定的に試す",
    "WATCH": "今後の動きを注視する",
    "WAIT": "条件が整うまで待つ",
    "AVOID": "現時点では採用を見送る",
}


class SnapshotError(ValueError):
    pass


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema") != SCHEMA:
        raise SnapshotError(f"schema must be {SCHEMA}")
    body_fields = sorted(FORBIDDEN_BODY_FIELDS & set(snapshot))
    if body_fields:
        raise SnapshotError(
            "existing prose is forbidden as Local Writer input: " + ", ".join(body_fields)
        )
    missing = [
        key for key in REQUIRED_FIELDS
        if key not in snapshot or snapshot.get(key) in (None, "", [])
    ]
    if missing:
        raise SnapshotError("missing required structured fields: " + ", ".join(missing))
    if str(snapshot["decision"]).upper() not in DECISION_PHRASES:
        raise SnapshotError("unsupported decision code")
    try:
        score = int(snapshot["decision_score"])
    except (TypeError, ValueError) as exc:
        raise SnapshotError("decision_score must be an integer") from exc
    if not 1 <= score <= 100:
        raise SnapshotError("decision_score must be 1..100")
    urls = snapshot["evidence_urls"]
    if not isinstance(urls, list) or not urls:
        raise SnapshotError("evidence_urls must be a non-empty list")
    if not all(isinstance(url, str) and url.startswith(("https://", "http://")) for url in urls):
        raise SnapshotError("evidence_urls must contain only HTTP(S) strings")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _decision_phrase(snapshot: Mapping[str, Any]) -> str:
    return DECISION_PHRASES[str(snapshot["decision"]).upper()]


def source_context(snapshot: Mapping[str, Any]) -> str:
    """Build the only factual context used by this local experiment."""
    validate_snapshot(snapshot)
    fields = (
        "reader_title",
        "name",
        "source_summary",
        "what",
        "why_important",
        "decision_reason",
        "action",
        "primary_risk",
        "best_for",
        "avoid_for",
    )
    rows = [f"{key}: {_clean(snapshot[key])}" for key in fields]
    rows.append("evidence_urls: " + " | ".join(snapshot["evidence_urls"]))
    return "\n".join(rows)


def render_body(snapshot: Mapping[str, Any]) -> str:
    """Compose one article from structured AIIF fields only.

    The prose between source fragments is deterministic editorial glue. It may
    explain the relationship among stored fields, but it must not introduce a
    new number, named entity, product, benchmark, causal claim, or experience.
    """
    validate_snapshot(snapshot)

    name = _clean(snapshot["name"])
    summary = _clean(snapshot["source_summary"])
    what = _clean(snapshot["what"])
    why = _clean(snapshot["why_important"])
    risk = _clean(snapshot["primary_risk"])
    best_for = _clean(snapshot["best_for"])
    avoid_for = _clean(snapshot["avoid_for"])
    reason = _clean(snapshot["decision_reason"])
    action = _clean(snapshot["action"])
    decision_phrase = _decision_phrase(snapshot)

    # One bounded topic heuristic improves the reader bridge without adding
    # factual content. The fallback remains generic for other snapshots.
    training_topic = "研修" in (what + why + risk + avoid_for + action)
    if training_topic:
        lead_bridge = (
            "「AIを使える状態」と「AIを使いこなせる状態」は、同じものとして扱わない方がよさそうです。"
            "今回の記録で見るべきなのは、AIそのものの性能より、使う側に残る差です。"
        )
        first_heading = "## 研修を増やす前に、見るべきものがある"
        decision_heading = "## 私なら、まず小さく確かめる"
    else:
        lead_bridge = (
            "今回の記録で大事なのは、名前や機能を覚えることではありません。"
            "何が観察され、どこまでなら判断に使えるのかを分けて読むことです。"
        )
        first_heading = "## まず、判断に効くところだけを見る"
        decision_heading = "## 私なら、この範囲から試す"

    parts = [
        f"{name}は、{summary}",
        "",
        what,
        "",
        lead_bridge,
        "",
        first_heading,
        "",
        why,
        "",
        (
            "ここで結論を強めすぎないことが大切です。"
            "保存済みの判断材料が示しているのは、利用の量だけでなく、使い方の質や業務文脈も見た方がよい、というところまでです。"
        ),
        "",
        best_for,
        "",
        "## ここは大きく一般化しない",
        "",
        risk,
        "",
        (
            "この制約がある以上、ひとつの観察結果を別の組織へそのまま移すのではなく、"
            "自社で何を確かめるべきかを決める材料として使う方が安全です。"
        ),
        "",
        avoid_for,
        "",
        decision_heading,
        "",
        f"AIIFの保存済み判断を読者向けに直すと、現時点では「{decision_phrase}」です。",
        "",
        reason,
        "",
        f"具体的な次の一手は、{action}",
        "",
        (
            "全面的な結論を急ぐより、まず限定した範囲で確かめる。"
            "結果が揃ってから広げるか、待つかを決める。この順番なら、保存済みEvidenceの範囲を越えません。"
        ),
        "",
        "## 結局、この記事から何を持ち帰るか",
        "",
        (
            "今回の価値は、ひとつの研究結果を万能な答えにすることではありません。"
            "どの情報を見て次の行動を決めるか、その順番をはっきりさせることです。"
        ),
        "",
        (
            "この研究だけで全社導入の答えを出すのではなく、社内で何を観察し、"
            "どんな小さな検証から始めるかを決める材料として使う。"
            "保存済みのEvidenceとActionをつなぐなら、その距離感がちょうどよいでしょう。"
        ),
        "",
        "### Sources / Evidence",
        "",
        f"- 発見経路: {_clean(snapshot['source'])}",
        *[f"- {url}" for url in snapshot["evidence_urls"]],
    ]
    return "\n".join(parts).strip() + "\n"


def render_article(snapshot: Mapping[str, Any]) -> str:
    validate_snapshot(snapshot)
    return f"# {_clean(snapshot['reader_title'])}\n\n{render_body(snapshot)}"


def to_pipeline_parsed(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Shape the Local Writer result like a normal parsed Writer payload.

    This is only for zero-provider Gate validation in the experiment. It does
    not persist or publish anything.
    """
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
