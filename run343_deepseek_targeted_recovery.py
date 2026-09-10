"""Run343 one-shot recovery for the exact DeepSeek V4.1 Flash article.

This is deliberately narrow and temporary. It reuses the canonical Production runtime
and all current Fact/Evidence/Publication/Reader gates, but replaces the generic
article_validation selector with one exact persisted candidate. Only an accepted result
is persisted; downstream note sync is owned by the workflow and runs only after this
process exits successfully.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation

TARGET_NAME = "DeepSeek launching v4.1 flash cheaper and more capable than v4 pro"
TARGET_URL = "https://news.ycombinator.com/item?id=49624603"


def _identity(item: dict[str, Any]) -> tuple[str, str]:
    repo = item.get("repo") or {}
    return str(repo.get("nameWithOwner") or ""), str(repo.get("url") or "")


def select_exact_target(pipeline) -> dict[str, Any]:
    rows = article_revalidation.select_revalidation_items(
        pipeline,
        limit=100,
        scan_limit=100,
        include_quality_failed=True,
    )
    if rows is None:
        raise RuntimeError("Run343 candidate read failed")
    matches = [row for row in rows if _identity(row) == (TARGET_NAME, TARGET_URL)]
    if len(matches) != 1:
        observed = [_identity(row) for row in rows]
        raise RuntimeError(
            f"Run343 exact target mismatch: expected one {(TARGET_NAME, TARGET_URL)!r}, "
            f"found={len(matches)} observed={observed!r}"
        )
    target = matches[0]
    if str(target.get("revalidation_content_status") or "") != str(pipeline.CONTENT_STATUS_QUALITY_FAILED):
        raise RuntimeError(
            "Run343 target is no longer Quality Failed; refusing mutation: "
            f"article={target.get('revalidation_article_status')!r} "
            f"content={target.get('revalidation_content_status')!r}"
        )
    return target


def run_targeted_recovery(pipeline) -> dict[str, Any]:
    budget = article_revalidation._cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[RUN343 TARGETED RECOVERY] exact=%s url=%s request_budget=%s persist=true",
        TARGET_NAME,
        TARGET_URL,
        budget,
    )
    item = select_exact_target(pipeline)
    repo = item.get("repo") or {}
    is_safe, license_status = pipeline.legal_safety_gate(repo)
    if not is_safe:
        raise RuntimeError(f"Run343 legal safety gate rejected target: {license_status}")

    generated = pipeline.generate_intelligence_report(
        repo,
        notion_page_id=item.get("notion_page_id"),
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", ""),
        candidate_rank=1,
        candidate_origin="new",
        attribution_context=item,
        persist_results=True,
    )
    if not generated:
        raise RuntimeError("Run343 target did not produce an accepted current-policy manuscript")
    manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
    if status != "accepted":
        raise RuntimeError(f"Run343 target remained non-Ready: status={status}")
    pipeline.logger.info(
        "[RUN343 TARGETED RECOVERY READY] %s chars=%s page=%s",
        TARGET_NAME,
        len(manuscript or ""),
        item.get("notion_page_id"),
    )
    return {"accepted": 1, "name": TARGET_NAME, "url": TARGET_URL}


def main() -> None:
    # production_pipeline installs the canonical current runtime before importing and
    # invoking article_revalidation.run_article_revalidation for article_validation.
    # Patch only that terminal selector/runner; all runtime layers and gates stay canonical.
    article_revalidation.run_article_revalidation = run_targeted_recovery
    os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
    import production_pipeline

    production_pipeline.main()


if __name__ == "__main__":
    main()
