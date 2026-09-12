"""Run257 thin extension over the byte-preserved Run255 Decision Intelligence core.

The Run255 implementation is stored verbatim in decision_intelligence_run255_core.py.
It is executed in this module's globals so existing patching/import behaviour remains
unchanged. Run256 overrides only the monthly Decision Brief renderer. Run257 adds a
fail-closed ownership guard around Technology Intelligence comment-like properties:
existing non-empty values are immutable and only owned blanks may be filled.
No schema, score/status semantics, Evidence gate, or provider-call policy is changed.
"""
from pathlib import Path as _Run256Path

from comment_write_contract import CommentWriteRequest, WriteDecision, decide_comment_write

_RUN256_CORE_PATH = _Run256Path(__file__).with_name("decision_intelligence_run255_core.py")
exec(compile(_RUN256_CORE_PATH.read_text(encoding="utf-8"), str(_RUN256_CORE_PATH), "exec"), globals(), globals())


def _run256_clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _run256_evidence_added(raw_row: dict, event: dict) -> str:
    existing = _run256_clean_text(event.get("evidence_added"))
    if existing:
        return existing
    props = raw_row.get("properties") or {}
    return _run256_clean_text(_rich_text_value(props.get(HISTORY_PROP_EVIDENCE_ADDED, {})))


def _run256_next_action(event: dict) -> str:
    status = str(event.get("adoption_status") or "").upper()
    return {
        "ADOPT": "導入条件と主リスクを確認し、導入判断を前へ進める。",
        "TEST": "限定検証を行い、その結果を次回の判断更新に使う。",
        "WATCH": "新しい一次情報と運用条件の変化を監視する。",
        "AVOID": "新規導入は見送り、再評価条件が満たされるまで保留する。",
    }.get(status, "新しい根拠が出た時点で判断を再確認する。")


def _run256_monitoring_point(events: list[dict]) -> str:
    for event in reversed(events):
        name = _run256_clean_text(event.get("technology_name") or event.get("canonical_entity_id"))
        status = _run256_clean_text(event.get("adoption_status")) or "UNKNOWN"
        detail = _run256_clean_text(
            event.get("evidence_added") or event.get("change_reason") or event.get("main_risk")
        )
        if name:
            suffix = f" 現時点の観測: {detail}" if detail else ""
            return (
                f"{name} は現在 {status}。{suffix.strip()} "
                f"次回はStatus変更、採用スコア±{MEANINGFUL_SCORE_DELTA}以上、または新規評価を確認する。"
            ).strip()
    return (
        "今月の履歴イベントはありません。"
        f"次回はStatus変更、採用スコア±{MEANINGFUL_SCORE_DELTA}以上、または新規評価の発生を確認する。"
    )


def _run256_compose_monthly_lines(events: list[dict], decision_brief: list[dict], period_id: str) -> list[str]:
    status_changes = [e for e in events if e.get("status_changed")]
    rises = sorted(
        [e for e in events if (e.get("score_delta") or 0) >= MEANINGFUL_SCORE_DELTA],
        key=lambda e: e.get("score_delta") or 0,
        reverse=True,
    )
    drops = sorted(
        [e for e in events if (e.get("score_delta") or 0) <= -MEANINGFUL_SCORE_DELTA],
        key=lambda e: e.get("score_delta") or 0,
    )
    new_assessments = [e for e in events if e.get("snapshot_type") == "INITIAL"]
    lines = [
        f"# 今月、何を再判断すべきか？ — {period_id}",
        "",
        f"意思決定イベント: {len(events)}件",
        f"新規評価: {len(new_assessments)}件",
        f"Status変更: {len(status_changes)}件",
        "",
        "## まず確認したい3件",
        "",
    ]
    if not decision_brief:
        lines.append("- **重要な判断変更なし** — 今月は既存判断を大きく変えるシグナルはありません。")
        lines.append(f"- **観測点** — {_run256_monitoring_point(events)}")
    else:
        for event in decision_brief:
            name = _run256_clean_text(event.get("technology_name") or event.get("canonical_entity_id")) or "名称未設定"
            previous = _run256_clean_text(event.get("previous_status")) or "NEW"
            current = _run256_clean_text(event.get("adoption_status")) or "UNKNOWN"
            delta = event.get("score_delta")
            delta_text = f" ({delta:+.0f})" if isinstance(delta, (int, float)) else ""
            reason = _run256_clean_text(event.get("change_reason") or event.get("main_risk")) or "履歴上の変更イベント"
            evidence = _run256_clean_text(event.get("evidence_added"))
            if not evidence:
                evidence = "追加根拠の記録なし。新しい根拠は断定しません。"
            lines.extend([
                f"### {name}",
                f"- 変更: {previous} → {current}{delta_text}",
                f"- 現在の判断: {event.get('decision_label') or _monthly_action_label(event)}",
                f"- 理由: {reason}",
                f"- 根拠: {evidence}",
                f"- 次のAction: {_run256_next_action(event)}",
                "",
            ])

    def add_section(title: str, items: list[dict], limit: int = 20) -> None:
        lines.extend([f"## {title}", ""])
        if not items:
            lines.append("- 該当なし")
        for event in items[:limit]:
            delta = event.get("score_delta")
            delta_text = f" ({delta:+.0f})" if isinstance(delta, (int, float)) else ""
            lines.append(
                f"- {event.get('technology_name') or event.get('canonical_entity_id')}: "
                f"{event.get('previous_status') or 'NEW'} → {event.get('adoption_status')}{delta_text} / "
                f"{event.get('change_reason')}"
            )
        lines.append("")

    add_section("Statusが変わったもの", status_changes)
    add_section("評価が上がったもの", rises)
    add_section("評価が下がったもの", drops)
    add_section("新規で評価したもの", new_assessments)
    return lines


def create_history_monthly_digest(period_id: str, generated_at: str | None = None) -> dict:
    """Create the existing monthly product with Run256 concrete/no-change Decision Update copy."""
    if not ENABLE_DECISION_MONTHLY_DIGEST:
        return {"enabled": False, "created": False, "period_id": period_id}
    if _monthly_exists(period_id):
        return {"enabled": True, "created": False, "period_id": period_id, "reason": "exists"}

    start, end = _month_bounds(period_id)
    rows = query_history_records(
        {"and": [
            {"property": HISTORY_PROP_REVIEWED_AT, "date": {"on_or_after": start}},
            {"property": HISTORY_PROP_REVIEWED_AT, "date": {"before": end}},
        ]},
        sorts=[{"property": HISTORY_PROP_REVIEWED_AT, "direction": "ascending"}],
        max_records=10000,
    )
    events: list[dict] = []
    for row in rows:
        event = dict(history_page_to_state(row))
        event["evidence_added"] = _run256_evidence_added(row, event)
        events.append(event)

    status_changes = [e for e in events if e.get("status_changed")]
    new_assessments = [e for e in events if e.get("snapshot_type") == "INITIAL"]
    decision_brief = build_monthly_decision_brief(events, limit=3)
    lines = _run256_compose_monthly_lines(events, decision_brief, period_id)
    summary = (
        f"{len(decision_brief)} reconsideration picks / {len(events)} decision events / "
        f"{len(status_changes)} status changes / {len(new_assessments)} new assessments"
    )
    now = generated_at or datetime.utcnow().isoformat() + "Z"
    props = {
        MONTHLY_PROP_TITLE: _title(f"今月、何を再判断すべきか？ {period_id}"),
        MONTHLY_PROP_PERIOD_ID: _rt(period_id),
        MONTHLY_PROP_GENERATED_AT: _date(now),
        MONTHLY_PROP_CHANGE_COUNT: _number(len(events)),
        MONTHLY_PROP_SUMMARY: _rt(summary),
    }
    children = []
    full = "\n".join(lines)
    for index in range(0, len(full), 1800):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": full[index:index + 1800]}}]},
        })
    res = requests.post(
        "https://api.notion.com/v1/pages",
        json={
            "parent": _parent(NOTION_MONTHLY_DATA_SOURCE_ID, NOTION_MONTHLY_DATABASE_ID),
            "properties": props,
            "children": children,
        },
        headers=_headers(),
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Decision monthly create failed: {res.status_code} {res.text[:500]}")
    return {
        "enabled": True,
        "created": True,
        "period_id": period_id,
        "events": len(events),
        "decision_brief_count": len(decision_brief),
        "page_id": res.json().get("id") or "",
    }


# Run257: preserve the existing product copy while allowing only owned blank fills.
# Keep this in the thin extension; decision_intelligence_run255_core.py remains byte-preserved.
_RUN257_COMMENT_FIELDS = {
    "main_risk": TECH_PROP_MAIN_RISK,
    "best_for": TECH_PROP_BEST_FOR,
    "avoid_for": TECH_PROP_AVOID_FOR,
    "short_rationale": TECH_PROP_SHORT_RATIONALE,
}
_RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE = upsert_technology_intelligence


def _run257_protect_existing_comment_fields(assessment: dict, existing_page: dict | None) -> dict:
    """Return a copy whose four product-copy fields obey the ownership contract."""
    if not existing_page:
        return dict(assessment)
    props = existing_page.get("properties") or {}
    protected = dict(assessment)
    for assessment_key, property_name in _RUN257_COMMENT_FIELDS.items():
        existing_value = _rich_text_value(props.get(property_name, {}))
        result = decide_comment_write(
            CommentWriteRequest(
                property_name=property_name,
                existing_value=existing_value,
                candidate_value=assessment.get(assessment_key),
                owner_allowed=True,
            )
        )
        if result.decision is WriteDecision.PRESERVE:
            protected[assessment_key] = result.value
        elif result.decision is WriteDecision.BLANK_FILL:
            protected[assessment_key] = result.value
        else:
            # Fail closed. A blocked/shadow candidate must not reach the production core.
            protected[assessment_key] = existing_value
    return protected


def upsert_technology_intelligence(assessment: dict, resolution: EntityResolution) -> dict:
    """Run257 guarded wrapper around the byte-preserved Run255 upsert."""
    if not ENABLE_DECISION_INTELLIGENCE_DB or resolution.status == "AMBIGUOUS":
        return _RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE(assessment, resolution)
    existing_page = get_technology_record_by_entity_id(resolution.entity_id)
    protected_assessment = _run257_protect_existing_comment_fields(assessment, existing_page)
    return _RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE(protected_assessment, resolution)
