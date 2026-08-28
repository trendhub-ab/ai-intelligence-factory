#!/usr/bin/env python3
"""Surgically reconcile Run134 Monthly Decision Brief onto latest main-derived branch.

Fail-closed: every anchor must occur exactly once. This preserves Run132 Context-First
and all existing Decision Intelligence persistence/schema behavior.
"""
from pathlib import Path


PATH = Path("decision_intelligence.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "def build_monthly_decision_brief(" in text:
        print("Run134 Monthly Decision Brief already present; no change")
        return

    function_anchor = '''def create_history_monthly_digest(period_id: str, generated_at: str | None = None) -> dict:\n'''
    function_replacement = '''def _monthly_decision_priority(event: dict) -> tuple[int, float, int]:
    """Deterministic priority for a member-facing reconsideration brief; no new factual inference."""
    status = str(event.get("adoption_status") or "").upper()
    previous = str(event.get("previous_status") or "").upper()
    delta = float(event.get("score_delta") or 0)
    status_weight = {"AVOID": 5, "ADOPT": 4, "TEST": 3, "WATCH": 2}.get(status, 1)
    changed = 1 if event.get("status_changed") else 0
    # Status changes outrank score-only movement; larger absolute changes outrank noise.
    return (changed * 10 + status_weight, abs(delta), 1 if previous and previous != status else 0)


def _monthly_action_label(event: dict) -> str:
    status = str(event.get("adoption_status") or "").upper()
    return {
        "ADOPT": "導入判断を前へ進める候補",
        "TEST": "限定検証を検討する候補",
        "WATCH": "今は待ち、監視を続ける候補",
        "AVOID": "導入を見送る／再確認する候補",
    }.get(status, "再確認候補")


def build_monthly_decision_brief(events: list[dict], limit: int = 3) -> list[dict]:
    """Pick only meaningful existing history events; never invent new recommendations."""
    meaningful = [
        e for e in events
        if e.get("status_changed") or abs(float(e.get("score_delta") or 0)) >= MEANINGFUL_SCORE_DELTA
        or e.get("snapshot_type") == "INITIAL"
    ]
    ranked = sorted(meaningful, key=_monthly_decision_priority, reverse=True)
    return [dict(e, decision_label=_monthly_action_label(e)) for e in ranked[:max(0, limit)]]


def create_history_monthly_digest(period_id: str, generated_at: str | None = None) -> dict:
'''
    text = replace_once(text, function_anchor, function_replacement, "monthly helper insertion")

    lines_anchor = '''    lines = [f"# What Changed? — {period_id}", "", f"意思決定イベント: {len(events)}件", f"新規評価: {len(new_assessments)}件", f"Status変更: {len(status_changes)}件", ""]\n    def add_section(title: str, items: list[dict], limit: int = 20):\n'''
    lines_replacement = '''    decision_brief = build_monthly_decision_brief(events, limit=3)
    lines = [f"# 今月、何を再判断すべきか？ — {period_id}", "", f"意思決定イベント: {len(events)}件", f"新規評価: {len(new_assessments)}件", f"Status変更: {len(status_changes)}件", "", "## まず確認したい3件", ""]
    if not decision_brief:
        lines.append("- 今月は、既存判断を大きく変えるシグナルはありません。")
    for e in decision_brief:
        delta = e.get("score_delta")
        delta_text = f" ({delta:+.0f})" if isinstance(delta, (int, float)) else ""
        transition = f"{e.get('previous_status') or 'NEW'} → {e.get('adoption_status') or 'UNKNOWN'}"
        reason = e.get("change_reason") or e.get("main_risk") or "履歴上の変更イベント"
        lines.append(f"- **{e.get('technology_name') or e.get('canonical_entity_id')}** — {e.get('decision_label')} / {transition}{delta_text} / {reason}")
    lines.append("")
    def add_section(title: str, items: list[dict], limit: int = 20):
'''
    text = replace_once(text, lines_anchor, lines_replacement, "monthly brief rendering")

    summary_anchor = '''    summary = f"{len(events)} decision events / {len(status_changes)} status changes / {len(new_assessments)} new assessments"\n'''
    summary_replacement = '''    summary = f"{len(decision_brief)} reconsideration picks / {len(events)} decision events / {len(status_changes)} status changes / {len(new_assessments)} new assessments"\n'''
    text = replace_once(text, summary_anchor, summary_replacement, "monthly summary")

    props_anchor = '''    props = {MONTHLY_PROP_TITLE: _title(f"What Changed? {period_id}"), MONTHLY_PROP_PERIOD_ID: _rt(period_id), MONTHLY_PROP_GENERATED_AT: _date(now), MONTHLY_PROP_CHANGE_COUNT: _number(len(events)), MONTHLY_PROP_SUMMARY: _rt(summary)}\n'''
    props_replacement = '''    props = {MONTHLY_PROP_TITLE: _title(f"今月、何を再判断すべきか？ {period_id}"), MONTHLY_PROP_PERIOD_ID: _rt(period_id), MONTHLY_PROP_GENERATED_AT: _date(now), MONTHLY_PROP_CHANGE_COUNT: _number(len(events)), MONTHLY_PROP_SUMMARY: _rt(summary)}\n'''
    text = replace_once(text, props_anchor, props_replacement, "monthly title")

    return_anchor = '''    return {"enabled": True, "created": True, "period_id": period_id, "events": len(events), "page_id": res.json().get("id") or ""}\n'''
    return_replacement = '''    return {"enabled": True, "created": True, "period_id": period_id, "events": len(events), "decision_brief_count": len(decision_brief), "page_id": res.json().get("id") or ""}\n'''
    text = replace_once(text, return_anchor, return_replacement, "monthly return payload")

    PATH.write_text(text, encoding="utf-8")
    print("Run134 Monthly Decision Brief reconciled successfully")


if __name__ == "__main__":
    main()
