#!/usr/bin/env python3
"""Run156: decision-grade External Review upgrade.

Re-review Run153 external backfill records using verified primary evidence while
preserving the production Product Review validator, entity identity and History.
Run156 adds paid-product context and lifecycle-consistency gates so a review
cannot be imported with thin copy or an adoption recommendation that contradicts
an explicit end-of-life statement in its own evidence-grounded decision context.

ZERO provider/Gemini calls: assessment prose is supplied by the external reviewer.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import context_first_enrichment
import decision_intelligence
import external_product_review_import

CONFIRM_TOKEN = "CONFIRM_RUN156_DECISION_REVIEW"
GENERIC_CONTEXT = {
    "生成AIモデル・モデル技術。",
    "AIエージェント開発基盤。",
    "AIアプリ・製品。",
    "AI実行・運用基盤。",
    "画像・音声・動画AI技術。",
    "AIデータ・検索基盤。",
    "AI開発支援ツール。",
    "AIセキュリティ評価技術。",
}

# Explicit lifecycle language that is incompatible with a positive new-adoption
# recommendation. Keep this intentionally narrow: it catches clear EOL states,
# not ordinary deprecations of individual APIs/features inside an active project.
HARD_EOL_MARKERS = (
    "archived",
    "no longer maintained",
    "no longer actively maintained",
    "no longer active",
    "maintenance mode",
    "read-only",
    "保守終了",
    "サポート終了",
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def validate_decision_density(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ctx = row.get("decision_context")
    review = row.get("review")
    if not isinstance(ctx, dict):
        return ["decision_context is required"]
    if not isinstance(review, dict):
        return ["review is required"]

    plain = _clean(ctx.get("plain_summary"))
    trigger = _clean(ctx.get("topic_trigger"))
    if len(plain) < 70:
        failures.append(f"plain_summary too short ({len(plain)}<70)")
    if len(plain) > 500:
        failures.append(f"plain_summary too long ({len(plain)}>500)")
    if plain in GENERIC_CONTEXT:
        failures.append("plain_summary is category-generic")
    if plain.count("。") + plain.count("！") + plain.count("？") < 2:
        failures.append("plain_summary must explain the item in at least two sentences")
    if len(trigger) < 45:
        failures.append(f"topic_trigger too short ({len(trigger)}<45)")
    if len(trigger) > 400:
        failures.append(f"topic_trigger too long ({len(trigger)}>400)")

    for key in ("main_risk", "best_for", "avoid_for", "short_rationale"):
        text = _clean(review.get(key))
        if len(text) < 45:
            failures.append(f"{key} too short ({len(text)}<45)")
    rationale = _clean(review.get("short_rationale"))
    if rationale.endswith("導入候補として比較する価値がある。") and len(rationale) < 90:
        failures.append("short_rationale is generic Run153-style copy")
    best = _clean(review.get("best_for"))
    if "ことを自社のAI導入・開発・運用で具体的に必要としているチーム" in best:
        failures.append("best_for contains malformed Run153 boilerplate")

    # Commercial safety: if the reviewer itself states that the project is
    # archived/maintenance-only/read-only, it cannot simultaneously tell a paid
    # subscriber to ADOPT/TEST it as a current new-adoption candidate.
    lifecycle_text = "\n".join((plain, trigger, rationale)).casefold()
    marker = next((m for m in HARD_EOL_MARKERS if m.casefold() in lifecycle_text), "")
    if marker:
        status = _clean(review.get("adoption_status")).upper()
        readiness = _clean(review.get("production_readiness")).upper()
        if status in {"ADOPT", "TEST"}:
            failures.append(
                f"lifecycle contradiction: explicit EOL marker '{marker}' cannot be {status}"
            )
        if readiness == "HIGH":
            failures.append(
                f"lifecycle contradiction: explicit EOL marker '{marker}' cannot have HIGH production_readiness"
            )
    return failures


def _load_rows(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("reviews") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Run156 input must be a list or {'reviews': [...]} object")
    return rows


def _patch_context(page_id: str, ctx: dict[str, Any], label: str) -> None:
    props = {
        context_first_enrichment.TECH_PROP_PLAIN_SUMMARY: context_first_enrichment._rt(_clean(ctx["plain_summary"])),
        context_first_enrichment.TECH_PROP_TOPIC_TRIGGER: context_first_enrichment._rt(_clean(ctx["topic_trigger"])),
    }
    context_first_enrichment._patch_context(page_id, props, label)


def _patch_subscribers(context_by_entity: dict[str, dict[str, Any]]) -> dict[str, int]:
    if not decision_intelligence.ENABLE_SUBSCRIBER_TECH_SYNC:
        return {"updated": 0, "missing": len(context_by_entity)}
    # First mirror score/status/risk/use-case fields through the existing sanitized sync.
    decision_intelligence.sync_subscriber_technology_db()
    pages = decision_intelligence._query_external_db(
        decision_intelligence.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID,
        decision_intelligence.NOTION_SUBSCRIBER_TECH_DATABASE_ID,
        max_records=5000,
    )
    by_entity: dict[str, dict] = {}
    for page in pages:
        props = page.get("properties") or {}
        entity_id = context_first_enrichment._text(props.get(decision_intelligence.SUB_PROP_ENTITY_ID))
        if entity_id and entity_id not in by_entity:
            by_entity[entity_id] = page
    updated = missing = 0
    for entity_id, ctx in context_by_entity.items():
        page = by_entity.get(entity_id)
        if not page:
            missing += 1
            continue
        props = {
            context_first_enrichment.SUB_PROP_PLAIN_SUMMARY: context_first_enrichment._rt(_clean(ctx["plain_summary"])),
            context_first_enrichment.SUB_PROP_TOPIC_TRIGGER: context_first_enrichment._rt(_clean(ctx["topic_trigger"])),
        }
        context_first_enrichment._patch_context(str(page.get("id") or ""), props, "Run156 Subscriber Decision Context")
        updated += 1
    return {"updated": updated, "missing": missing}


def run(path: str, *, apply: bool, audit_path: str) -> dict[str, Any]:
    rows = _load_rows(path)
    density_failures = []
    for row in rows:
        failures = validate_decision_density(row)
        if failures:
            density_failures.append({"name": row.get("name"), "failures": failures})
    if density_failures:
        report = {"run": "Run156", "mode": "apply" if apply else "validate", "zero_gemini_calls": True,
                  "density_gate": "failed", "failures": density_failures}
        Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
        Path(audit_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    base_audit = str(Path(audit_path).with_name(Path(audit_path).stem + "_product_review.json"))
    base = external_product_review_import.run(
        path, apply=apply, target=0, max_rows=len(rows), audit_path=base_audit
    )
    report: dict[str, Any] = {
        "run": "Run156 Decision Density Upgrade",
        "mode": "apply" if apply else "validate",
        "zero_gemini_calls": True,
        "density_gate": "passed",
        "input_count": len(rows),
        "product_review": base,
    }
    if not apply:
        report["validated"] = base.get("validated", 0)
    else:
        row_by_name = {str(r.get("name") or ""): r for r in rows}
        context_by_entity: dict[str, dict[str, Any]] = {}
        internal_updated = 0
        for item in base.get("results") or []:
            if not item.get("saved"):
                continue
            row = row_by_name.get(str(item.get("name") or ""))
            entity_id = str(item.get("entity_id") or "")
            page_id = str(item.get("page_id") or "")
            if not row or not entity_id or not page_id:
                continue
            ctx = row["decision_context"]
            _patch_context(page_id, ctx, "Run156 Technology Decision Context")
            context_by_entity[entity_id] = ctx
            internal_updated += 1
        subscriber = _patch_subscribers(context_by_entity)
        report.update({
            "saved": base.get("saved", 0),
            "internal_context_updated": internal_updated,
            "subscriber_context_updated": subscriber["updated"],
            "subscriber_context_missing": subscriber["missing"],
        })
    Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
    Path(audit_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["validate", "apply"])
    p.add_argument("--input", required=True)
    p.add_argument("--audit-path", default="external_review_artifacts/run156_decision_density.json")
    p.add_argument("--confirm", default="")
    a = p.parse_args()
    apply = a.mode == "apply"
    if apply and a.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")
    report = run(a.input, apply=apply, audit_path=a.audit_path)
    print(json.dumps({k: report.get(k) for k in (
        "mode", "zero_gemini_calls", "density_gate", "input_count", "validated", "saved",
        "internal_context_updated", "subscriber_context_updated", "subscriber_context_missing"
    )}, ensure_ascii=False))
    if report.get("density_gate") != "passed":
        return 2
    if not apply and report.get("validated") != report.get("input_count"):
        return 3
    if apply and report.get("saved") != report.get("input_count"):
        return 4
    if apply and report.get("subscriber_context_missing"):
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
