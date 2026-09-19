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
Run406 adds one extra Reader-only repair only in this exact approved lane when the first
Reader Repair has already run, Reader-only weakness remains, Evidence is safe, and the
existing request budget still permits a call. It does not increase that budget.
Run408 fixes a provider-routing blind spot only in this approved lane: a model rejected
by the persistent safety counter before provider send no longer consumes one of Run260's
two configured fallback positions and strand an available later model.
Run409 fixes retry-owner ordering only in this approved lane: after the ordinary quality
retry is spent, safe Reader-only blockers can still claim Run360's already-existing
dedicated Reader Repair slot instead of being masked by base-retry exhaustion.
Run410 keeps the same explicit approval boundary after a fail-closed quality result moves
the exact page from Pending Retry to Quality Failed. It can reconstruct only the single
owner-approved page id, only when its live title and lifecycle still match. It never scans
or substitutes arbitrary Quality Failed stock assets.

No note.com action occurs here. A successful Notion/Ready persistence is handed to the
existing zero-model note-ready synchronization flow afterwards.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation
import run400_approved_reader_repair
import run406_approved_second_reader_repair
import run408_approved_quality_fallback
import run409_approved_reader_owner_bridge

APPROVAL_TOKEN = "APPLY_APPROVED_ARTICLE"
DEFAULT_EXPECTED_NAME = "OpenAI agents carried out an undisclosed attack on RubyGems"
DEFAULT_EXPECTED_PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"


def _approval_is_valid() -> bool:
    return os.environ.get("ARTICLE_REVALIDATION_APPLY_CONFIRM", "").strip() == APPROVAL_TOKEN


def _expected_name() -> str:
    return os.environ.get("ARTICLE_REVALIDATION_EXPECTED_NAME", DEFAULT_EXPECTED_NAME).strip()


def _expected_page_id() -> str:
    return os.environ.get("ARTICLE_REVALIDATION_EXPECTED_PAGE_ID", DEFAULT_EXPECTED_PAGE_ID).strip()


def _select_name(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _number(prop: dict | None) -> int | None:
    value = (prop or {}).get("number")
    return int(value) if isinstance(value, (int, float)) else None


def _read_exact_quality_failed_target(pipeline, expected: str, expected_page_id: str) -> dict[str, Any] | None:
    """Read only the explicitly approved page when it is live Quality Failed/Deep Dive.

    This is intentionally not a Quality Failed collection query. The owner-approved page
    id is the lookup key, and the live title/lifecycle are revalidated before reconstruction.
    """
    if not expected_page_id:
        raise RuntimeError("Run410 expected page id is required")
    requests_mod = getattr(pipeline, "requests", None)
    headers_fn = getattr(pipeline, "_notion_headers", None)
    plain_fn = getattr(pipeline, "_notion_plain_text", None)
    if requests_mod is None or not callable(headers_fn) or not callable(plain_fn):
        raise RuntimeError("Run410 requires canonical Notion page read helpers")

    try:
        response = requests_mod.get(
            f"https://api.notion.com/v1/pages/{expected_page_id}",
            headers=headers_fn(),
            timeout=10,
        )
    except Exception as exc:
        raise RuntimeError(f"Run410 approved page read failed: {exc}") from exc
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(f"Run410 approved page read failed: status={getattr(response, 'status_code', None)}")

    page = response.json() or {}
    live_page_id = str(page.get("id") or "").strip()
    if live_page_id != expected_page_id:
        raise RuntimeError("Run410 approved page id mismatch")
    props = page.get("properties") or {}

    prop_name = getattr(pipeline, "PROP_NAME", "記事名")
    prop_url = getattr(pipeline, "PROP_URL", "元情報URL")
    prop_source = getattr(pipeline, "PROP_SOURCE", "情報源")
    prop_summary = getattr(pipeline, "PROP_SOURCE_SUMMARY", "元情報要約")
    prop_content = getattr(pipeline, "PROP_CONTENT_STATUS", "コンテンツ状態")
    prop_article = getattr(pipeline, "PROP_ARTICLE_STATUS", "記事状態")
    prop_eval = getattr(pipeline, "PROP_EVALUATION_STATUS", "評価状態")
    prop_score = getattr(pipeline, "PROP_SCREENING_SCORE", "選別スコア")
    prop_reason = getattr(pipeline, "PROP_SCREENING_REASON", "選別理由")
    prop_engagement = getattr(pipeline, "PROP_ENGAGEMENT", "注目度")

    live_name = plain_fn(props.get(prop_name) or {})
    if live_name != expected:
        raise RuntimeError(f"Run410 approved page title mismatch: expected={expected!r} actual={live_name!r}")

    article_status = _select_name(props.get(prop_article))
    content_status = _select_name(props.get(prop_content))
    evaluation_status = _select_name(props.get(prop_eval))
    ready = str(getattr(pipeline, "ARTICLE_STATUS_READY", "Ready"))
    quality_failed = str(getattr(pipeline, "CONTENT_STATUS_QUALITY_FAILED", "Quality Failed"))
    pending_retry = str(getattr(pipeline, "CONTENT_STATUS_PENDING_RETRY", "Pending Retry"))
    deep_dive = str(getattr(pipeline, "CONTENT_STATUS_DEEP_DIVE", "Deep Dive"))
    if article_status == ready:
        raise RuntimeError("Run410 refuses an approved page that is already Ready")
    if content_status not in {quality_failed, pending_retry}:
        return None
    if evaluation_status and evaluation_status != deep_dive:
        raise RuntimeError(
            f"Run410 approved page is not Deep Dive: content={content_status!r} evaluation={evaluation_status!r}"
        )

    raw_url = props.get(prop_url) or {}
    source_url = str(raw_url.get("url") or plain_fn(raw_url) or "").strip()
    source = _select_name(props.get(prop_source)) or plain_fn(props.get(prop_source) or {})
    summary = plain_fn(props.get(prop_summary) or {})
    screening_score = _number(props.get(prop_score))
    screening_reason = plain_fn(props.get(prop_reason) or {})
    engagement = _number(props.get(prop_engagement)) or 0
    repo = {
        "nameWithOwner": live_name,
        "originalTitle": live_name,
        "html_url": source_url,
        "url": source_url,
        "description": summary,
        "sourceSummary": summary,
        "source": source,
        "engagement": engagement,
    }
    return {
        "notion_page_id": live_page_id,
        "repo": repo,
        "screening_score": screening_score,
        "screening_reason": screening_reason,
        "approved_target_source": (
            "pending_retry_exact" if content_status == pending_retry else "quality_failed_exact"
        ),
    }


def _select_exact_approved_target(pipeline, expected: str, expected_page_id: str = "") -> dict[str, Any]:
    """Resolve one approved target without ever substituting a different stock asset."""
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
            if expected_page_id and page_id and page_id != expected_page_id:
                continue
            dedupe_key = page_id or f"{source}:{actual}"
            if dedupe_key in seen_page_ids:
                continue
            seen_page_ids.add(dedupe_key)
            row["approved_target_source"] = source
            matches.append(row)

    # Run410: only when the normal bounded sources no longer contain the exact page,
    # read the explicitly approved page id itself. Never query the wider Quality Failed set.
    if not matches and expected_page_id:
        exact_failed = _read_exact_quality_failed_target(pipeline, expected, expected_page_id)
        if exact_failed is not None:
            matches.append(exact_failed)

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
    run409_approved_reader_owner_bridge.install(pipeline)
    run406_approved_second_reader_repair.install(pipeline)
    run408_approved_quality_fallback.install(pipeline)

    expected = _expected_name()
    expected_page_id = _expected_page_id()
    if not expected:
        raise RuntimeError("Run399 expected article name is required")
    if not expected_page_id:
        raise RuntimeError("Run410 expected page id is required")

    request_budget = article_revalidation._cap_validation_budget(pipeline)
    item = _select_exact_approved_target(pipeline, expected, expected_page_id)
    repo = item.get("repo") or {}
    actual = str(repo.get("nameWithOwner") or "").strip()
    if actual != expected:
        raise RuntimeError(f"Run399 target mismatch: expected={expected!r} actual={actual!r}")

    page_id = str(item.get("notion_page_id") or "").strip()
    if not page_id:
        raise RuntimeError("Run399 target has no Notion page id")
    if page_id != expected_page_id:
        raise RuntimeError(f"Run410 target page mismatch: expected={expected_page_id!r} actual={page_id!r}")

    current = article_revalidation._read_current_statuses(pipeline, page_id)
    if current is None:
        raise RuntimeError("Run399 could not re-read current target lifecycle")
    article_status, content_status = current
    if article_status == pipeline.ARTICLE_STATUS_READY:
        raise RuntimeError("Run399 refuses an article that is already Ready")

    continuation = content_status == pipeline.CONTENT_STATUS_PENDING_RETRY
    quality_failed_continuation = content_status == pipeline.CONTENT_STATUS_QUALITY_FAILED
    source = str(item.get("approved_target_source") or "")
    if continuation and source not in {"pending_retry", "pending_retry_exact"}:
        raise RuntimeError("Run399 Pending Retry lifecycle must come from canonical pending source or exact approved pending source")
    if quality_failed_continuation and source != "quality_failed_exact":
        raise RuntimeError("Run410 Quality Failed lifecycle must come from exact approved page source")

    safe, license_status = pipeline.legal_safety_gate(repo)
    if not safe:
        raise RuntimeError(f"Run399 legal safety gate failed: {license_status}")

    pipeline.logger.warning(
        "[RUN399 APPROVED APPLY] target=%s page_id=%s source=%s request_budget=%s prior_article=%s prior_content=%s pending_continuation=%s quality_failed_continuation=%s persist=true",
        actual,
        page_id,
        source,
        request_budget,
        article_status,
        content_status,
        continuation,
        quality_failed_continuation,
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
        "quality_failed_continuation": quality_failed_continuation,
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
