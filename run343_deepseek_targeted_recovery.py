"""Run343f one-shot recovery for the exact DeepSeek V4.1 Flash article.

This temporary route binds to one exact Notion page and re-verifies page id, title,
canonical source URL, source, and lifecycle before any provider call or mutation.
A prior provider-unavailable attempt may legitimately move this exact item from
Quality Failed to Pending Retry, so only those two non-Ready recovery states are
accepted. Every other lifecycle state still fails closed.

Run260 intentionally prepends the canonical Production 3.7/3.8 routing even when a
workflow supplies a narrower environment pool. For this one exact recovery only,
Run343f therefore pins the *effective installed pipeline module pool* immediately
before generation. Global Production routing and Daily remain unchanged.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation

TARGET_PAGE_ID = "3d7479ff-dca9-81eb-9256-ca37b93d410f"
TARGET_NAME = "DeepSeek launching v4.1 flash cheaper and more capable than v4 pro"
TARGET_URL = "https://news.ycombinator.com/item?id=49624603"
TARGET_SOURCE = "HackerNews"
ALLOWED_RECOVERY_CONTENT_STATUSES = {"Quality Failed", "Pending Retry"}
TARGET_MODEL_POOL = ("gemini-3.6-flash", "gemini-3.5-flash")


def _rich_text(prop: dict[str, Any] | None) -> str:
    value = prop or {}
    rows = value.get("title") or value.get("rich_text") or []
    return "".join(str(row.get("plain_text") or "") for row in rows).strip()


def _select(prop: dict[str, Any] | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _url(prop: dict[str, Any] | None) -> str:
    return str((prop or {}).get("url") or "").strip()


def _number(prop: dict[str, Any] | None) -> float | int | None:
    return (prop or {}).get("number")


def _date_start(prop: dict[str, Any] | None) -> str:
    return str(((prop or {}).get("date") or {}).get("start") or "").strip()


def candidate_from_page_payload(pipeline, payload: dict[str, Any]) -> dict[str, Any]:
    props = (payload or {}).get("properties") or {}
    name = _rich_text(props.get("記事名"))
    source_url = _url(props.get("元情報URL"))
    primary_url = _url(props.get("一次情報URL"))
    source = _select(props.get("情報源"))
    content_status = _select(props.get("コンテンツ状態"))
    article_status = _select(props.get("記事状態"))

    quality_failed = str(pipeline.CONTENT_STATUS_QUALITY_FAILED)
    allowed_statuses = {quality_failed, "Pending Retry"}
    mismatches = []
    if str((payload or {}).get("id") or "").replace("-", "") != TARGET_PAGE_ID.replace("-", ""):
        mismatches.append("page_id")
    if name != TARGET_NAME:
        mismatches.append("title")
    if source_url != TARGET_URL:
        mismatches.append("source_url")
    if primary_url and primary_url != TARGET_URL:
        mismatches.append("primary_url")
    if source != TARGET_SOURCE:
        mismatches.append("source")
    if content_status not in allowed_statuses:
        mismatches.append("content_status")
    if article_status == str(getattr(pipeline, "ARTICLE_STATUS_READY", "Ready")):
        mismatches.append("already_ready")
    if mismatches:
        raise RuntimeError(
            "Run343f exact Notion target contract changed; refusing provider call/mutation: "
            + ",".join(mismatches)
        )

    screening_score = _number(props.get("選別スコア"))
    if screening_score is None:
        screening_score = _number(props.get("判断スコア"))
    screening_reason = _rich_text(props.get("選別理由")) or _rich_text(props.get("スコア内訳"))
    description = _rich_text(props.get("元情報要約"))
    engagement = _number(props.get("注目度"))
    published_at = _date_start(props.get("公開日"))

    repo = {
        "nameWithOwner": TARGET_NAME,
        "name": TARGET_NAME,
        "url": TARGET_URL,
        "source": TARGET_SOURCE,
        "description": description,
        "engagement": engagement or 0,
        "publishedAt": published_at,
        "published_at": published_at,
    }
    return {
        "repo": repo,
        "notion_page_id": TARGET_PAGE_ID,
        "screening_score": screening_score,
        "screening_reason": screening_reason,
        "source_url": TARGET_URL,
        "revalidation_article_status": article_status,
        "revalidation_content_status": content_status,
    }


def read_exact_target(pipeline) -> dict[str, Any]:
    try:
        response = pipeline.requests.get(
            f"https://api.notion.com/v1/pages/{TARGET_PAGE_ID}",
            headers=pipeline._notion_headers(),
            timeout=10,
        )
    except Exception as exc:
        raise RuntimeError(f"Run343f exact Notion page read failed: {exc}") from exc
    if int(getattr(response, "status_code", 0) or 0) != 200:
        raise RuntimeError(
            f"Run343f exact Notion page read failed HTTP {getattr(response, 'status_code', 0)}"
        )
    return candidate_from_page_payload(pipeline, response.json() or {})


def pin_effective_target_model_pool(pipeline) -> list[str]:
    """Pin only this installed runtime to 3.6 -> 3.5 and prove the effective value."""
    target = list(TARGET_MODEL_POOL)
    pipeline.DEEP_DIVE_MODEL_POOL = list(target)
    pipeline.DEEP_DIVE_MODEL_CANDIDATES = list(target)
    if hasattr(pipeline, "SELECTED_DEEP_DIVE_MODEL"):
        pipeline.SELECTED_DEEP_DIVE_MODEL = target[0]

    effective_pool = [str(v).strip() for v in getattr(pipeline, "DEEP_DIVE_MODEL_POOL", []) if str(v).strip()]
    effective_candidates = [
        str(v).strip() for v in getattr(pipeline, "DEEP_DIVE_MODEL_CANDIDATES", []) if str(v).strip()
    ]
    if effective_pool != target or effective_candidates != target:
        raise RuntimeError(
            "Run343f effective model pool pin failed; refusing provider call: "
            f"pool={effective_pool!r} candidates={effective_candidates!r}"
        )
    return effective_pool


def run_targeted_recovery(pipeline) -> dict[str, Any]:
    budget = article_revalidation._cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[RUN343F TARGETED RECOVERY] page=%s exact=%s url=%s request_budget=%s persist=true",
        TARGET_PAGE_ID, TARGET_NAME, TARGET_URL, budget,
    )
    item = read_exact_target(pipeline)
    repo = item["repo"]
    pipeline.logger.info(
        "[RUN343F TARGET VERIFIED] page=%s status=%s/%s score=%s source=%s",
        TARGET_PAGE_ID,
        item.get("revalidation_article_status"),
        item.get("revalidation_content_status"),
        item.get("screening_score"),
        repo.get("source"),
    )
    is_safe, license_status = pipeline.legal_safety_gate(repo)
    if not is_safe:
        raise RuntimeError(f"Run343f legal safety gate rejected target: {license_status}")

    effective_pool = pin_effective_target_model_pool(pipeline)
    pipeline.logger.warning(
        "[RUN343F EFFECTIVE MODEL POOL] %s",
        ",".join(effective_pool),
    )

    generated = pipeline.generate_intelligence_report(
        repo,
        notion_page_id=TARGET_PAGE_ID,
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", ""),
        candidate_rank=1,
        candidate_origin="new",
        attribution_context=item,
        persist_results=True,
    )
    if not generated:
        raise RuntimeError("Run343f target did not produce an accepted current-policy manuscript")
    manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
    if status != "accepted":
        raise RuntimeError(f"Run343f target remained non-Ready: status={status}")
    pipeline.logger.info(
        "[RUN343F TARGETED RECOVERY READY] %s chars=%s page=%s",
        TARGET_NAME, len(manuscript or ""), TARGET_PAGE_ID,
    )
    return {"accepted": 1, "page_id": TARGET_PAGE_ID, "name": TARGET_NAME, "url": TARGET_URL}


def main() -> None:
    article_revalidation.run_article_revalidation = run_targeted_recovery
    os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
    import production_pipeline
    production_pipeline.main()


if __name__ == "__main__":
    main()
