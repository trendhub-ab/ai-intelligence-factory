#!/usr/bin/env python3
"""Run399: apply one explicitly approved revalidated article through Production.

This is deliberately narrower than full Production and deliberately stronger than
read-only article_validation:
- exact owner-approved target name is required;
- exactly one existing non-Ready candidate is selected;
- the normal Production runtime/gates are installed by production_pipeline.main();
- the same bounded Deep Dive request budget is used;
- persistence is enabled only in this explicit entrypoint;
- the command fails unless the regenerated article returns status=accepted.

No note.com action occurs here. A successful Notion/Ready persistence is handed to the
existing zero-model note-ready synchronization flow afterwards.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation

APPROVAL_TOKEN = "APPLY_APPROVED_ARTICLE"
DEFAULT_EXPECTED_NAME = "OpenAI agents carried out an undisclosed attack on RubyGems"


def _approval_is_valid() -> bool:
    return os.environ.get("ARTICLE_REVALIDATION_APPLY_CONFIRM", "").strip() == APPROVAL_TOKEN


def _expected_name() -> str:
    return os.environ.get("ARTICLE_REVALIDATION_EXPECTED_NAME", DEFAULT_EXPECTED_NAME).strip()


def run_approved_article_apply(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Regenerate and persist exactly one pre-approved existing non-Ready article."""
    if not _approval_is_valid():
        raise RuntimeError("Run399 approval token is missing or invalid")

    expected = _expected_name()
    if not expected:
        raise RuntimeError("Run399 expected article name is required")

    request_budget = article_revalidation._cap_validation_budget(pipeline)
    items = article_revalidation.select_revalidation_items(
        pipeline,
        limit=1,
        scan_limit=article_revalidation.DEFAULT_SCAN_LIMIT,
        include_quality_failed=True,
    )
    if items is None:
        raise RuntimeError("Run399 candidate read failed")
    if len(items) != 1:
        raise RuntimeError(f"Run399 requires exactly one candidate, got {len(items)}")

    item = dict(items[0])
    repo = item.get("repo") or {}
    actual = str(repo.get("nameWithOwner") or "").strip()
    if actual != expected:
        raise RuntimeError(f"Run399 target mismatch: expected={expected!r} actual={actual!r}")

    page_id = str(item.get("notion_page_id") or "").strip()
    if not page_id:
        raise RuntimeError("Run399 target has no Notion page id")

    current = article_revalidation._read_current_statuses(pipeline, page_id)
    if current is None:
        raise RuntimeError("Run399 could not re-read current target lifecycle")
    article_status, content_status = current
    if article_status == pipeline.ARTICLE_STATUS_READY:
        raise RuntimeError("Run399 refuses an article that is already Ready")
    if content_status == pipeline.CONTENT_STATUS_PENDING_RETRY:
        raise RuntimeError("Run399 refuses Pending Retry ownership")

    safe, license_status = pipeline.legal_safety_gate(repo)
    if not safe:
        raise RuntimeError(f"Run399 legal safety gate failed: {license_status}")

    pipeline.logger.warning(
        "[RUN399 APPROVED APPLY] target=%s page_id=%s request_budget=%s prior_article=%s prior_content=%s persist=true",
        actual,
        page_id,
        request_budget,
        article_status,
        content_status,
    )

    generated = pipeline.generate_intelligence_report(
        repo,
        notion_page_id=page_id,
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", ""),
        candidate_rank=1,
        candidate_origin="approved_article_apply",
        attribution_context=item,
        persist_results=True,
    )
    if not generated:
        raise RuntimeError("Run399 target produced no manuscript")

    manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
    if status != "accepted":
        raise RuntimeError(f"Run399 target did not pass current Production gates: status={status}")

    result = {
        "selected": 1,
        "generated": 1,
        "accepted": 1,
        "rejected": 0,
        "target": actual,
        "notion_page_id": page_id,
        "chars": len(manuscript or ""),
    }
    pipeline.logger.info("[RUN399 APPROVED APPLY COMPLETE] %s", result)
    return result


def main() -> None:
    if not _approval_is_valid():
        raise SystemExit("Run399 refused: approval token missing")
    # Reuse the canonical Production installer and article_validation orchestration slot;
    # only the selected lane function is replaced before production_pipeline imports it.
    article_revalidation.run_article_revalidation = run_approved_article_apply
    os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
    import production_pipeline

    production_pipeline.main()


if __name__ == "__main__":
    main()
