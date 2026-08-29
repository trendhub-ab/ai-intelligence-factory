#!/usr/bin/env python3
"""Run153: zero-Gemini External Product Review Import.

Purpose
-------
Allow a human/admin external reviewer (for example ChatGPT) to supply the same
Product Review JSON contract used by the normal Gemini path, while preserving
all existing evidence, validation, entity-resolution, History and Notion
persistence semantics.

This module NEVER calls Gemini. Primary evidence is re-fetched and checked by
existing production code before any write. Invalid/unsupported reviews fail
closed. Context-First enrichment runs after successful imports.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import context_first_enrichment
import decision_intelligence
import pipeline

CONFIRM_TOKEN = "CONFIRM_EXTERNAL_REVIEW_IMPORT"
DEFAULT_AUDIT_PATH = "external_review_artifacts/run153_external_review_import.json"


def _forbid_gemini(*_args, **_kwargs):
    raise RuntimeError("Run153 External Review Import forbids Gemini/provider calls")


# Hard runtime guard. If any future refactor accidentally routes this path through
# a provider call, fail immediately instead of spending quota.
pipeline._generate_via_chat = _forbid_gemini


def _load_rows(path: str) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = raw.get("reviews") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("External review file must be a list or {'reviews': [...]} object")
    return rows


def _repo_from_row(row: dict[str, Any]) -> dict:
    name = str(row.get("name") or row.get("nameWithOwner") or "").strip()
    url = str(row.get("url") or "").strip()
    if not name or not url:
        raise ValueError("Each external review requires name and url")
    source = str(row.get("source") or "GitHub").strip()
    details = dict(row.get("source_details") or row.get("sourceDetails") or {})
    primary = str(row.get("primary_url") or row.get("primaryUrl") or url).strip()
    return pipeline.normalize_item(
        source=source,
        name=name,
        url=url,
        description=str(row.get("description") or "").strip(),
        engagement=int(row.get("engagement") or 0),
        license_info=row.get("license_info"),
        published_at=row.get("published_at"),
        source_context="",
        primary_url=primary,
        source_details=details,
    )


def _assessed_snapshot() -> dict[str, str | None]:
    snapshot: dict[str, str | None] = {}
    for page in decision_intelligence.query_technology_records(max_records=5000):
        state = decision_intelligence.technology_page_to_state(page)
        entity_id = str(state.get("canonical_entity_id") or "")
        if entity_id:
            snapshot[entity_id] = state.get("last_reviewed")
    return snapshot


def _assessed_count() -> int:
    total = 0
    for page in decision_intelligence.query_technology_records(max_records=5000):
        state = decision_intelligence.technology_page_to_state(page)
        if state.get("assessment_state") == "ASSESSED" and state.get("tracking_status") != "ARCHIVED":
            total += 1
    return total


def _prepare_verified_evidence(repo: dict) -> tuple[dict, dict, list[str]]:
    source_info = pipeline.prepare_source_context(repo)
    evidence = pipeline.assess_evidence_sufficiency(source_info)
    if evidence.get("state") == pipeline.EVIDENCE_SUPPLEMENT_REQUIRED:
        source_info = pipeline.supplement_source_evidence(source_info)
        evidence = pipeline.assess_evidence_sufficiency(source_info)
    authority_failures = pipeline._primary_source_authority_failures(source_info)
    return source_info, evidence, authority_failures


def _validate_review_against_evidence(parsed: dict, source_info: dict, evidence: dict) -> tuple[bool, list[str]]:
    verification_context = source_info.get("verification_context") or source_info.get("context", "")
    return pipeline.validate_decision_intelligence_assessment(
        parsed,
        evidence,
        verification_context,
        source_info.get("evidence_metadata", {}),
    )


def process_row(row: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    repo = _repo_from_row(row)
    review = row.get("review")
    if not isinstance(review, dict):
        raise ValueError(f"{repo['nameWithOwner']}: review object is required")

    # Reuse the exact production structured-output validator/normalizer.
    parsed = pipeline._parse_product_review_response(review)
    source_info, evidence, authority_failures = _prepare_verified_evidence(repo)
    result: dict[str, Any] = {
        "name": repo.get("nameWithOwner"),
        "url": repo.get("url"),
        "category": parsed.get("category"),
        "adoption_score": parsed.get("adoption_score"),
        "mode": "apply" if apply else "validate",
        "saved": False,
    }
    if authority_failures:
        result.update(status="skipped_authority", failures=authority_failures)
        return result
    if evidence.get("state") == pipeline.EVIDENCE_INSUFFICIENT or not evidence.get("decision_scope_safe"):
        result.update(
            status="skipped_evidence",
            failures=list(evidence.get("blocking_missing") or []),
        )
        return result

    ok, failures = _validate_review_against_evidence(parsed, source_info, evidence)
    if not ok:
        result.update(status="invalid_assessment", failures=failures)
        return result
    if not apply:
        result.update(status="validated", evidence_state=evidence.get("state"))
        return result

    reviewed_at = datetime.now(timezone.utc).isoformat()
    persisted = pipeline.persist_decision_intelligence_assessment(
        repo,
        parsed,
        source_info,
        evidence,
        reviewed_at,
        screening_score=row.get("screening_score"),
        screening_reason=str(row.get("screening_reason") or "External reviewer backfill"),
        attribution_context={"portfolio_topic": parsed.get("category") or "OTHER"},
        pipeline_status="External Review Import",
        content_status="Stocked",
        article_status=pipeline.ARTICLE_STATUS_NOT_PLANNED,
    )

    # Preserve the production Run114 source-boundary repair behavior without
    # relaxing any gate and without a provider call.
    boundary_failures = pipeline._source_boundary_failure_names(persisted.get("failures") or [])
    if (not persisted.get("saved") and persisted.get("reason") == "assessment_invalid" and boundary_failures):
        reconciliation = pipeline.reconcile_product_review_source_boundary(
            parsed, source_info, persisted.get("failures") or []
        )
        result["boundary_reconciliation"] = reconciliation
        if reconciliation.get("resolved"):
            evidence = pipeline.assess_evidence_sufficiency(source_info)
            ok, failures = _validate_review_against_evidence(parsed, source_info, evidence)
            if ok:
                persisted = pipeline.persist_decision_intelligence_assessment(
                    repo,
                    parsed,
                    source_info,
                    evidence,
                    reviewed_at,
                    screening_score=row.get("screening_score"),
                    screening_reason=str(row.get("screening_reason") or "External reviewer backfill"),
                    attribution_context={"portfolio_topic": parsed.get("category") or "OTHER"},
                    pipeline_status="External Review Import",
                    content_status="Stocked",
                    article_status=pipeline.ARTICLE_STATUS_NOT_PLANNED,
                )
            else:
                persisted = {"saved": False, "reason": "assessment_invalid", "failures": failures}

    result.update(
        status="saved" if persisted.get("saved") else str(persisted.get("reason") or "not_saved"),
        saved=bool(persisted.get("saved")),
        created=bool(persisted.get("created")),
        entity_id=persisted.get("entity_id"),
        page_id=persisted.get("page_id"),
        failures=persisted.get("failures") or [],
    )
    return result


def run(path: str, *, apply: bool, target: int, max_rows: int, audit_path: str) -> dict[str, Any]:
    decision_intelligence.preflight_decision_intelligence_schema()
    context_first_enrichment.preflight_context_first_schema()
    previous_reviewed = _assessed_snapshot()
    before = _assessed_count()
    estimated_assessed = before
    rows = _load_rows(path)
    results: list[dict[str, Any]] = []

    # Do not re-query the full Notion DB before every row. New backfill candidates
    # normally create one assessed entity each; duplicates are explicitly not counted
    # in this local estimate. The authoritative count is re-read once after the batch.
    for row in rows[: max(0, max_rows) if max_rows else None]:
        if apply and target > 0 and estimated_assessed >= target:
            break
        try:
            item_result = process_row(row, apply=apply)
            results.append(item_result)
            if apply and item_result.get("saved") and item_result.get("created"):
                estimated_assessed += 1
        except Exception as exc:
            results.append({
                "name": str(row.get("name") or row.get("nameWithOwner") or "unknown"),
                "status": "error",
                "saved": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    enrichment = {"enabled": False}
    if apply and any(r.get("saved") for r in results):
        enrichment = context_first_enrichment.enrich_context_first(previous_reviewed)
    after = _assessed_count() if apply else before
    report = {
        "run": "Run153 External Product Review Import",
        "zero_gemini_calls": True,
        "mode": "apply" if apply else "validate",
        "input": path,
        "before_assessed": before,
        "after_assessed": after,
        "target": target,
        "processed": len(results),
        "saved": sum(1 for r in results if r.get("saved")),
        "created": sum(1 for r in results if r.get("created")),
        "validated": sum(1 for r in results if r.get("status") == "validated"),
        "skipped_or_failed": sum(1 for r in results if not r.get("saved") and r.get("status") != "validated"),
        "enrichment": enrichment,
        "results": results,
    }
    target_path = Path(audit_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["validate", "apply"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--audit-path", default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()
    apply = args.mode == "apply"
    if apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")
    report = run(
        args.input,
        apply=apply,
        target=max(0, args.target),
        max_rows=max(0, args.max_rows),
        audit_path=args.audit_path,
    )
    print(json.dumps({k: report[k] for k in (
        "mode", "before_assessed", "after_assessed", "processed", "saved", "created", "validated", "skipped_or_failed", "zero_gemini_calls"
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
