#!/usr/bin/env python3
"""Run399: apply one explicitly approved revalidated article through Production.

This is deliberately narrower than full Production and deliberately stronger than
read-only article_validation:
- exact owner-approved target name is required;
- exactly one matching existing candidate is selected from bounded canonical sources;
- the normal Production runtime/gates are installed by production_pipeline.main();
- the same bounded Deep Dive request budget is used;
- persistence is enabled only in this explicit entrypoint;
- the command fails unless the regenerated article returns status=accepted.

Run400 adds no new quality policy. It lets this approved-only origin reuse the already
bounded Run208/360 Reader Repair contract when Evidence is safe and a request remains.
Run402 makes target selection exact-name based rather than "first eligible" based.
Run403 also reads the canonical Pending Retry source because those rows are deliberately
absent from the generic Deep Dive regeneration list after a fail-closed persistence event.

No note.com action occurs here. A successful Notion/Ready persistence is handed to the
existing zero-model note-ready synchronization flow afterwards.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation
import run400_approved_reader_repair

APPROVAL_TOKEN = "APPLY_APPROVED_ARTICLE"
DEFAULT_EXPECTED_NAME = "OpenAI agents carried out an undisclosed attack on RubyGems"


def _approval_is_valid() -> bool:
    return os.environ.get("ARTICLE_REVALIDATION_APPLY_CONFIRM", "").strip() == APPROVAL_TOKEN


def _expected_name() -> str:
    return os.environ.get("ARTICLE_REVALIDATION_EXPECTED_NAME", DEFAULT_EXPECTED_NAME).strip()


def _select_exact_approved_target(pipeline, expected: str) -> dict[str, Any]:
    """Resolve exactly one approved target across canonical bounded candidate sources."""
    deep_rows = pipeline.get_regen_test_items(article_revalidation.DEFAULT_SCAN_LIMIT, "")
    if deep_rows is None:
        raise RuntimeError("Run399 Deep Dive candidate read failed")

    pending_reader = getattr(pipeline, "get_pending_retry_items", None)
    if not callable(pending_reader):
        raise RuntimeError("Run399 requires canonical get_pending_retry_items")
    pending_rows = pending_reader(article_revalidation.DEFAULT_SCAN_LIMIT)
    if pending_rows is None:
        raise RuntimeError("Run399 Pending Retry candidate read failed")

    matches: list[dict[str, Any]] = []
    seen_page_ids: set[str] = set()
    for source, rows in (("deep_dive", deep_rows), ("pending_retry", pending_rows)):
        for raw in rows:
            row = dict(raw or {})
            repo = row.get("repo") or {}
            actual = str(repo.get("nameWithOwner") or "").strip()
            if actual != expected:
                continue
            page_id = str(row.get("notion_page_id") or "").strip()
            dedupe_key = page_id or f"{source}:{actual}"
            if dedupe_key in seen_page_ids:
                continue
            seen_page_ids.add(dedupe_key)
            row["approved_target_source"] = source
            matches.append(row)

    if len(matches) != 1:
        raise RuntimeError(
            f"Run399 exact target count mismatch: expected_name={expected!r} matches={len(matches)}"
        )
    return matches[0]


def run_approved_article_apply(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Regenerate and persist exactly one pre-approved existing non-Ready article."""
    if not _approval_is_valid():
        raise RuntimeError("Run399 approval token is missing or invalid")

    run400_approved_reader_repair.install(pipeline)

    expected = _expected_name()
    if not expected:
        raise RuntimeError("Run399 expected article name is required")

    request_budget = article_revalidation._cap_validation_budget(pipeline)
    item = _select_exact_approved_target(pipeline, expected)
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

    continuation = content_status == pipeline.CONTENT_STATUS_PENDING_RETRY
    source = str(item.get("approved_target_source") or "")
    if continuation and source != "pending_retry":
        raise RuntimeError("Run399 Pending Retry lifecycle must come from canonical pending source")

    safe, license_status = pipeline.legal_safety_gate(repo)
    if not safe:
        raise RuntimeError(f"Run399 legal safety gate failed: {license_status}")

    pipeline.logger.warning(
        "[RUN399 APPROVED APPLY] target=%s page_id=%s source=%s request_budget=%s prior_article=%s prior_content=%s pending_continuation=%s persist=true",
        actual,
        page_id,
        source,
        request_budget,
        article_status,
        content_status,
        continuation,
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
        "pending_continuation": continuation,
        "target_source": source,
    }
    pipeline.logger.info("[RUN399 APPROVED APPLY COMPLETE] %s", result)
    return result


def main() -> None:
    if not _approval_is_valid():
        raise SystemExit("Run399 refused: approval token missing")
    article_revalidation.run_article_revalidation = run_approved_article_apply
    os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
    import production_pipeline

    production_pipeline.main()


if __name__ == "__main__":
    main()
